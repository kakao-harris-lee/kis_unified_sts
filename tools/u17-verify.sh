#!/usr/bin/env bash
# u17-verify-v222e5 (gen-2 = v2.22 에라타 5차 ⓦⓧ · 계약 fd13ca26) — 레인 1 증거 실행기
# ── gen-1/gen-2 «공통» 델타 (레인 1 증거 도구 · v2.22 에라타 (b)② ) ──────────────────────
#   (b)② 블록을 통째로 교체한다:
#     ① 열거 규율 인지 fetch — `?filter=all&per_page=100`(계약 리터럴) + `--paginate`
#        + `--paginate --slurp`(페이지 수 N·페이지별 원소 수를 «본문»에서) + 종단 프로브 `?page=<N+1>`
#     ② 열거 완전성 limb 술어 호출 — 불충족 = `PREVENTION_UNVERIFIABLE`(전순서 1 · 8 로 접지 않는다)
#     ③ (b)② «4단 사다리» 술어 호출 — 1단계 E · 2단계 완결성(두 축 «각각») · 3단계 «현행» C · 4단계 ∀-success
#     ④ 층 (2) 를 단일 `RUN_ID` → **`∀ r ∈ R`** 로 교체 (per-run `len(hit_r)==1` · 2차 ⓝ ·
#        run 간 «합산» 금지 · «선택»을 구현 재량으로 두지 않는다 — 선택 규칙은 사다리 3단계가 핀한다)
#   **gen-1 ↔ gen-2 의 차이는 «술어 파일 이름 2개 + 위 제목 줄 1개» 뿐이다** — derive-e45.py 가 diff 로 강제한다.
#   그 밖의 전 축은 **코드 델타 0**(격리 스냅샷 · host 결속 C6 · PARENTS-UNTRUSTED · (a) 술어 ·
#    countersign · P_first/P_last · (b-blob)@target/@d 정본 잡 대조 · 연속성 α · 전순서 10단 · trap EXIT).
# ── 이하 v2.22 동결 8ec22754 원문 헤더 ────────────────────────────────────────────────
# u17-verify (v2.22 동결 8ec22754) — U-17 «예방 통제 활성 증거» 실행기 (계약 8ec22754 §12.3.4 U-17)
#   v2.21 동결 0528a919 실행기(sha256 5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727)
#   에서 파생 — 델타는 **v2.21 재심 처분 4건 + C-1 + M-4/M-2/M-1/M-3** 뿐이고, 그 밖의 전 축은
#   **코드 델타 0**(격리 스냅샷 · host 결속 C6 · PARENTS-UNTRUSTED ㉠㉡㉢ · SHALLOW · (a) 술어 ·
#    countersign · P_first/P_last E9/E11 · 연속성 α · 전순서 10단 · trap EXIT 폐쇄 · responder seam).
#     [F#1 — #1 «회피» 2연속 :5689-5747]  정본 `steps` 순서 반전 [① 체크아웃 · ② 정본 B(sha256 «검증»)
#           · ③ 정본 A(하니스 «실행»)] + 3축(`if:`·`continue-on-error` 키 부재·`SHELL_OK`).
#           **정본 A/B 코드펜스의 «내용»과 두 스텝 `name:` 리터럴은 byte 불변** — 바뀐 것은 순서뿐이다.
#     [M-7 — #2 부분해소 3연속 :5828-5877]  **(b)③ blob 층에 `D` 무관 «무조건 항» `(b-blob)@target` 추가.**
#           `branches/<target>` → `.commit.sha` 를 해석해 **transcript 에 verbatim 수록(필수)** 한 뒤
#           `contents/<wf>?ref=<target HEAD sha>` 를 정본 잡 템플릿과 대조한다.  **«추가»이지 «대체»가
#           아니다** — 기존 D-지표 항 `(b-blob)@d`(`?ref=<PR head.sha>`)는 그대로 유지한다(N-11).
#           404·HTTP 오류 → `PREVENTION_UNVERIFIED_REVISION`(ABSENT 로 접지 않는다) · 네트워크·인증
#           오류 → `PREVENTION_UNVERIFIABLE`.
#     [F#2 — 신규 high :5659-5671·5787-5793]  게이트 체크/잡 이름을 **아티팩트 파라미터에서 계약
#           리터럴 `tos-gate` 로 이동**(선언 3항→2항).  blob 층 `jobs`=1 ∧ 잡 id·`name` 값-핀 ·
#           서버 층 이름 필터 `hit` 의 `len(hit)!=1` → UNVERIFIED_REVISION (술어 파일 소관).
#     [M-3 :5557-5565]  (b)② **path-aware check-run 전수 열거** — 동명 check-run 을 conclusion 으로
#           «먼저 거르지 않고» 전부 열거해 각각을 워크플로 run 으로 해석하고, **정본 `path` 인 것이
#           «정확히 1개» ∧ 그것이 `success`** 여야 한다.  v2.21 은 `conclusion==success` 로 먼저 걸러
#           첫 후보만 봤다 — 그래서 «정본 fail + decoy success» 가 통과했다.
#           **동명·다른 path 의 공존 자체는 red 가 아니다** — 열거 기록만 남긴다((a) 동명 decoy 잔여).
#     [C-1 / M-4 / M-2 / F#4 / M-1]  술어 파일 교체: wfcanon-v221.py → **wfcanon-v222.py**
#           (전 노드 중복 키 검출 · `yq --version` 파서 핀 · `<<` 금지 · 최상위 allowlist ·
#            `permissions`/`runs-on`/checkout `with` 값 전수 핀 · `on` ⊆ {pull_request, push}).
#           PyYAML compose 층이 필요하므로 그 술어만 `$PYBIN`(.venv) 로 돈다 — 실행기 자신의
#           inline JSON 헬퍼는 **`python3` 그대로**(코드 델타 0).
# ── 이하 v2.21 원문 헤더 ─────────────────────────────────────────────────────────
# u17-verify (v2.21 동결 0528a919) — U-17 «예방 통제 활성 증거» 실행기 (계약 0528a919 §12.3.4 U-17)
#   v2.20/에라타 ae842cce 실행기(sha256 67d636ce...) 에서 파생 — 델타는 **v2.21 심판 #1 처분 1건**뿐이다:
#     [(b)3 :5467-5510] «구조 파싱(자작 토크나이저)» -> **«정본 대조»**(YAML 파서 + 정규화 후 byte 비교).
#       술어 파일 교체: wfstruct-v220.py -> wfcanon-v221.py (자작 셸 토크나이저·명령 위치 판별기 폐기 —
#       운영자 «바퀴 재발명 금지» 지침·CLAUDE.md Development Discipline).  서버 잡 스텝 대조(2)·격리 스냅샷·
#       host 결속·U-17-c 10값은 v2.20 거동 그대로(코드 델타 0).
#   v2.19 에라타 6차 실행기(359f5bc5·sha256 174b0c18...) 에서 파생 — 델타는 **v2.20 심판 처분 2건**뿐이다:
#     [#1 — (b)3 :5452-5486] «두 리터럴 grep» -> **구조 파싱 + 서버 스텝 대조** 2층.
#           (1) 서버 blob 을 YAML 파서로 구조 파싱해 jobs.<게이트 잡>.steps[] 의 run: «실행문만» 소비
#               (셸 토크나이즈·# 주석[full-line·trailing] 제거·bash -n 파스 — wfstruct-v220.py)
#           (2) actions/runs/{run_id}/jobs 의 그 잡 conclusion==success 이고 계약 리터럴 두 «스텝 이름»이
#               각각 conclusion==success 로 실재 — 부재·실패 -> PREVENTION_UNVERIFIED_REVISION (T-84 14)
#     [#3 — [PARENTS-UNTRUSTED] :7098-7124] **격리 스냅샷 기층** — 조상성·부모·blob 소비를 진입 시점 HEAD 의
#           git clone --no-local --no-hardlinks (+GIT_NO_REPLACE_OBJECTS=1) 스냅샷 «안에서만» 수행하고,
#           스냅샷 청정성(제2 공집합·grafts 부재·제1 일치)을 canary 로 방출한다.  clone 실패는 **fail-closed**.
#           원 저장소 관측은 «리뷰 보조»로 격하돼 기록만 남는다.
#   v2.19 에라타 5차 실행기(eddbd241·sha256 cd3e9e1e…) 에서 파생 — 델타는 **에라타 6차 [E15] 1건**뿐이다:
#     [E15 — stop-time BLOCK] 파생 경로 결합 base 를 **«저장소 루트(`git rev-parse --show-toplevel`)»만**으로 고정한다.
#           **`--absolute-git-dir` 결합은 «철회»** — `<root>/.git` + `.git/info/grafts` = **이중 `.git`**(`<root>/.git/.git/info/grafts`)
#           이라 실제 graft 를 «거짓 ABSENT» 로 읽고 ㉡ 이 통과 = **fail-open**(stop-time 실측·addendum-5 가 이를 «fail-closed»로 오분류).
#     [E15 극성 규율] **«거짓 부재(ABSENT)»가 «검사를 통과»시키면 그것은 fail-open 이다** — 부재의 극성은 «검사 방향»이 정한다.
#           `--git-path` 절대 출력(`--separate-git-dir`·linked worktree)은 **그대로** 쓴다(결합 금지).  동등 대안: `git -C <루트> rev-parse --git-path <x>` + 그 cwd 검사.
#   (E1~E14 는 eddbd241 실행기 거동 그대로 — 이 실행기는 이미 `--show-toplevel` 결합만 쓴다·코드 델타 0, 주석·헤더만.)
#   (E1·E2·E3·E6·E8②·E9·E10·E11 은 f6493d23 실행기 거동 그대로 — 코드 델타 0.)
#   (E1·E2·E3·E6·E8②·E9 는 ad5be1a3 실행기 거동 그대로 — 코드 델타 0.)
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=…` 라인이 연다.  전순서 10단 · exit 0 = ACTIVE 만 · trap EXIT 폐쇄.
# 사용: bash u17-verify-v219.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
PIN_HOST=${CANON%%/*}                                 # [C6] 핀 host — 계약 핀에서 «파생»(아티팩트 선언 아님)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=f5651fadcf2b5acda97192677525517751ff176eeaaccea4b5a446055e5670f1   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
WFCANON="${U17_WFCANON:-$(dirname "$0")/wfcanon-v222.py}"     # [v2.22] «정본 잡 템플릿» 술어 (C-1 전 노드 중복 + 파서 핀 + 값 전수 핀)
PYBIN="${U17_PYBIN:-/Users/harris/Development/private/kis_unified_sts/.venv/bin/python}"  # [v2.22] 술어의 PyYAML compose 층 전용 (시스템 python3 에는 PyYAML 부재)
LADDER="${U17_LADDER:-$(dirname "$0")/ladder-v222e5.py}"       # [레인1] (b)② 4단 사다리 술어 — **gen 차이 자리**
PAGELIMB="${U17_PAGELIMB:-$(dirname "$0")/pagelimb-v222e5.py}" # [레인1] 열거 완전성 limb 술어 — **gen 차이 자리**
PAGE_MODE="${U17_PAGE_MODE:-loose}"                   # [레인1] limb ② 독법 strict|loose — gen-1 전용 피연산자(gen-2 는 «무동작»)
GATE_JOB=tos-gate                                     # [v2.22·F#2/N-4] 계약 리터럴 — 잡 id == 표시 이름 == required context (아티팩트 파라미터 아님)
INHERITED_GH_HOST="${GH_HOST-∅(미설정)}"              # [C6] 재핀 «전» 상속값 기록
export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
export GIT_NO_REPLACE_OBJECTS=1     # [E8] ② 무력화 — 모든 조상·부모 파생 git 호출이 replace 뷰를 따르지 않는다
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
rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; PREVENTION_CONTINUITY_UNVERIFIABLE) echo 9;; *) echo 99;; esac; }
FIRED=""; NF=0; fire() { NF=$((NF+1)); FIRED="$FIRED$1|$2"$'\n'; printf 'U17-fire %s: %s\n' "$1" "$2"; }
finish() { local best="" bestr=99 f s r; while IFS= read -r f; do [ -n "$f" ] || continue; s=${f%%|*}; r=$(rank "$s"); if [ "$r" -lt "$bestr" ]; then bestr=$r; best="$f"; fi; done <<< "$FIRED"
  if [ -n "$best" ]; then emit "${best%%|*}" "${best#*|} [수집 ${NF}건 중 전순서 최소]"; fi; emit PREVENTION_ACTIVE "$1"; }

# ── responder seam  ([C6] gh 경로의 모든 조회에 --hostname <핀 host> 명시 · 헤더 별도 보존)
respond() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body" hd="$CAP/$k.hdr"
  case "$RESP" in
    gh)  local out; out=$(gh api -i --hostname "$PIN_HOST" "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
         printf '%s\n' "$out" | awk '/^\r?$/{exit} {print}' | tr -d '\r' > "$hd"
         printf '%s\n' "$out" | awk 'f{print} /^\r?$/{f=1}' | tr -d '\r' > "$bd"
         if ! grep -Eq '^[0-9]{3}$' "$st"; then printf 'ERR\n' > "$st"; cat "$CAP/$k.err" > "$bd" 2>/dev/null; return 1; fi; return 0 ;;
    file:*) local dir="${RESP#file:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; : > "$hd"; return 1; fi ;;
    mixed:*) local dir="${RESP#mixed:}"
         if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         else printf 'U17-seam %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond "$path"; local r=$?; RESP="$save"; return $r; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
# ── [레인1 · 5차 ⓧ(ㄱ)] `--paginate --slurp` seam — 응답 «모양»이 바뀌는 유일한 자리.
#    본문이 «페이지 배열의 배열» 이 되어 페이지 수 N 과 페이지별 원소 수가 «본문에서» 관측된다.
#    `respond` 와 «별도 키»(`<key>.slurp.*`)에 보존한다 — 같은 URL 의 두 조회를 섞지 않는다.
respond_slurp() {
  local path="$1" k; k=$(key "$1"); local st="$CAP/$k.slurp.status" bd="$CAP/$k.slurp.body"
  case "$RESP" in
    gh)  if gh api --hostname "$PIN_HOST" --paginate --slurp "$path" > "$bd" 2>"$CAP/$k.slurp.err"; then printf '200\n' > "$st"; return 0
         else printf 'ERR\n' > "$st"; cat "$CAP/$k.slurp.err" > "$bd" 2>/dev/null; return 1; fi ;;
    file:*|mixed:*) local dir="${RESP#*:}"
         if [ -f "$dir/$k.slurp.status" ]; then cp "$dir/$k.slurp.status" "$st"; cp "$dir/$k.slurp.body" "$bd" 2>/dev/null || : > "$bd"
           grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
         elif [ "${RESP%%:*}" = mixed ]; then printf 'U17-seam --slurp %s ← gh(live)\n' "$path"; local save="$RESP"; RESP=gh; respond_slurp "$path"; local r=$?; RESP="$save"; return $r
         else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected --slurp response for %s\n' "$path" > "$bd"; return 1; fi ;;
    *) emit PREVENTION_UNVERIFIABLE "알 수 없는 responder: $RESP" ;;
  esac
}
show_slurp() { local k; k=$(key "$1"); printf 'U17-B2s --slurp %s  utc=%s  status=%s  (본문 = 페이지 배열의 배열)\n' "$1" "$(utc)" "$(cat "$CAP/$k.slurp.status" 2>/dev/null)"; sed 's/^/  | /' "$CAP/$k.slurp.body" 2>/dev/null; }
reqid() { grep -i '^X-GitHub-Request-Id:' "$CAP/$(key "$1").hdr" 2>/dev/null | head -1 | tr -d '\r' | sed 's/^[Xx]-[Gg]it[Hh]ub-[Rr]equest-[Ii]d:[[:space:]]*//'; }
show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s  x-github-request-id=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")" "$(reqid "$2")"; sed 's/^/  | /' "$CAP/$k.body"; }
jget() { python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1]))
    for kk in sys.argv[2].split("."):
        j=j[int(kk)] if isinstance(j,list) else j[kk]
    print(j if not isinstance(j,(dict,list)) else json.dumps(j))
except Exception: print("")' "$CAP/$(key "$1").body" "$2" 2>/dev/null; }
http_of() { cat "$CAP/$(key "$1").status" 2>/dev/null; }
ok2xx() { printf '%s' "$1" | grep -Eq '^2'; }
# ── [PARENTS-UNTRUSTED / E8] 부모 집합 신뢰 판별 — (1) 얕은 경계(국소) · (2) 재작성(전역 관측)
# [E13] 저장소 내부 경로는 «파생»만 — 리터럴 `.git/…` 금지.  (`--git-path` 는 일반 배치에서 상대 경로를 주므로 cwd=repo 전제 · L-1)
# [E14+E15] 파생 + «결합»: 상대면 **저장소 루트(--show-toplevel)** 와 결합, 절대면 그대로.  cwd 상대 검사 금지 · --absolute-git-dir 결합 금지(이중 .git = 거짓 ABSENT = fail-open).
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null || printf '.')
# [v2.20 D-γ] 결합 base 를 «호출 시점»에 파생한다 — 격리 스냅샷으로 cwd 가 바뀐 뒤 캐시된 TOPLEVEL 을 쓰면
#   스냅샷의 grafts 를 «원 저장소 경로»로 검사해 «거짓 ABSENT» 가 된다(E15 극성 규율의 재발 표면).
gitpath() { local v t; v=$(git rev-parse --git-path "$1" 2>/dev/null); t=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$TOPLEVEL"); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$t" "$v";; esac; }
GITDIR_ABS=$(git rev-parse --absolute-git-dir 2>/dev/null || printf '')
SHALLOW_PATH=$(gitpath shallow); GRAFTS_PATH=$(gitpath info/grafts)
IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
SHALLOW_LIST=$( [ -f "$SHALLOW_PATH" ] && tr '\n' ' ' < "$SHALLOW_PATH" || printf '' )
REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
have_commit() { git cat-file -e "$1^{commit}" 2>/dev/null; }
# ── [E10 ㉠] 주 판별 — 부모 집합 «구조 재파생»(커밋 객체의 parent 줄 직접 파싱).  판정의 모든 ∀p 항이 이것을 쓴다.
parents_true() { git --no-replace-objects cat-file commit "$1" 2>/dev/null | awk '/^$/{exit} /^parent /{printf "%s ", $2}'; }
# ── [E10 ㉠ 대조] «이력 뷰»가 주는 부모 — 무력화를 «걷어내고» 관측한다(재작성 여부를 보려면 뷰를 그대로 봐야 한다)
parents_ambient() { env -u GIT_NO_REPLACE_OBJECTS git log --format=%P -1 "$1" 2>/dev/null; }
nset() { printf '%s\n' $1 | sort | tr '\n' ' '; }
# 함수는 «명령 치환 서브셸»에서 도므로 결과를 변수로 되돌릴 수 없다 — 파일로 누적한다.
PUF=$(mktemp); PUC=$(mktemp); PUL=$(mktemp); : > "$PUF"; : > "$PUC"; : > "$PUL"
# [E12] 절차 순서 = ㉢ 먼저: 얕은 경계로 «특정»되는 불일치는 국소 귀속($PUL)하고, «남는» 것만 전역($PUF)으로 올린다.
check_parents() { local x="$1" tp ap b
  printf '%s\n' "$x" >> "$PUC"
  tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")")
  [ "$tp" = "$ap" ] && return 0
  for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && { printf '%s[㉢ 얕은 경계 귀속 — 재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUL"; return 0; }; done
  printf '%s[재파생=(%s) vs 뷰=(%s)]\n' "$x" "${tp% }" "${ap% }" >> "$PUF"; return 1; }
# ── [E10 ㉢] 국소 — 그 커밋의 부모 «객체»가 미상인가 (E6: 전역 단축 아님)
is_boundary() { local x="$1" b p; for b in $SHALLOW_LIST; do [ "$b" = "$x" ] && return 0; done
  for p in $(parents_true "$x"); do have_commit "$p" || return 0; done; return 1; }

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"
# ── [v2.20 — 심판 #3] 격리 스냅샷 기층 (계약 3d17ea66 :7098-7124) ─────────────────────────────
#   조상성·부모·blob 을 소비하는 «모든» 판정을 진입 시점 HEAD 의 격리 스냅샷 «안에서만» 수행한다.
#   원격 관측(위 [C3])은 원 저장소 «설정»이라 스냅샷 «전»에 끝내고, 아래부터는 스냅샷이 기층이다.
ORIGIN=$(pwd -P); ENTRY_HEAD=$(git rev-parse HEAD 2>/dev/null || printf '')
printf 'U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[%s] · %s=%s · is_shallow=%s · entry HEAD=%s\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${ENTRY_HEAD:-∅}"
[ -n "$ENTRY_HEAD" ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 시점 HEAD 파생 불가"
SNAPBASE=$(mktemp -d); SNAP="$SNAPBASE/snap"
printf 'U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks %s %s\n' "$ORIGIN" "$SNAP"
GIT_NO_REPLACE_OBJECTS=1 git clone --quiet --no-local --no-hardlinks "$ORIGIN" "$SNAP" 2>"$CAP/clone.err"; CRC=$?
printf 'U17-SNAP clone rc=%s\n' "$CRC"; [ -s "$CAP/clone.err" ] && sed 's/^/  | /' "$CAP/clone.err"
[ "$CRC" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] clone 실패(rc=$CRC) — 정직 경계 (a): 원본 grafts 가 참 부모를 도달 불가로 만들면 스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed)"
git -C "$SNAP" cat-file -e "$ENTRY_HEAD^{commit}" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD($ENTRY_HEAD) 가 스냅샷에 부재 — 핀 실패 fail-closed"
git -C "$SNAP" checkout --quiet --detach "$ENTRY_HEAD" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD 체크아웃 실패"
cd "$SNAP" || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 스냅샷 진입 실패"
# ㉠㉡㉢ 는 스냅샷 «안에서» 재파생한다 (계약: 스냅샷 안 ㉡ = 기층이 깨끗함을 고정하는 canary)
SHALLOW_PATH=$(gitpath shallow); GRAFTS_PATH=$(gitpath info/grafts)
IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
SHALLOW_LIST=$( [ -f "$SHALLOW_PATH" ] && tr '\n' ' ' < "$SHALLOW_PATH" || printf '' )
REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
CAN_MIS=0; for x in $(git rev-list --all 2>/dev/null); do
  tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")"); [ "$tp" = "$ap" ] || CAN_MIS=$((CAN_MIS+1)); done
printf 'U17-SNAP canary(스냅샷 «안»): HEAD=%s · replace -l=[%s] · %s=%s · is_shallow=%s · ㉠(cat-file 부모 == %%P) 불일치 %s건 / 커밋 %s개\n' \
  "$(git rev-parse HEAD)" "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$CAN_MIS" "$(git rev-list --all | grep -c .)"
[ "$CAN_MIS" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷 canary] 스냅샷 안에서 ㉠ 불일치 ${CAN_MIS}건 — 기층 오염(--local 폴백·번들 오용 표면)"


# ── [C6 ①] 전제: 핀 host 인증  (responder=file 은 live 조회가 없으므로 SIMULATED 로 기록만)
AUTHRC=0; AUTHOUT=""; AUTHMODE=live
AUTHCMD="gh auth status --hostname $PIN_HOST"                     # [C6] 표시·사유 문자열 (대조군은 이 줄과 다음 줄이 함께 바뀐다)
case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status --hostname "$PIN_HOST" 2>&1); AUTHRC=$? ;; esac

# ── [C2] Actions app id 서버 파생 · [C3] target = 핀 repo default_branch  (A00·A0)
respond "apps/github-actions"; ST_APP=$(http_of "apps/github-actions"); APPID=$(jget "apps/github-actions" id)
respond "repos/$PIN_OR";       ST0=$(http_of "repos/$PIN_OR");          TARGET=$(jget "repos/$PIN_OR" default_branch)
printf 'U17-0 target=%s@%s\n' "$PIN_OR" "${TARGET:-UNRESOLVED}"
printf 'U17-0 pin=%s remotes:%s match=%s | actions_app_id=%s (apps/github-actions http=%s) | responder=%s capture_dir=%s\n' "$CANON" "${NORMED:- (none)}" "${MATCH_REMOTE:-∅}" "${APPID:-∅}" "$ST_APP" "$RESP" "$CAP"
printf 'U17-H [C6] pin_host=%s (계약 핀에서 파생) · 상속 GH_HOST=%s → 현행 GH_HOST=%s · auth 전제 `%s` → mode=%s rc=%s\n' "$PIN_HOST" "$INHERITED_GH_HOST" "${GH_HOST-∅(재핀 없음)}" "$AUTHCMD" "$AUTHMODE" "$AUTHRC"
if [ "$AUTHMODE" = live ]; then printf '%s\n' "$AUTHOUT" | sed 's/^/  | /'; else printf '  | (responder=%s — live 조회 없음: 주입 응답 위 결정적 술어)\n' "$RESP"; fi
[ "$AUTHMODE" != live ] || [ "$AUTHRC" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[C6] \`$AUTHCMD\` 실패(rc=$AUTHRC) — 핀 host 인증 부재 (타 host 폴백 없음)"
# [E8 ①] 전역 관측 — 부모 «재작성» 축 (replace ref · info/grafts 파생 경로).  얕음은 국소(E6)라 여기서 발화하지 않는다.
printf 'U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[%s] · %s(--git-path 파생)=%s · ㉢ is_shallow=%s · %s(--git-path 파생) 목록=[%s] · git-dir=%s · 무력화 GIT_NO_REPLACE_OBJECTS=%s · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄\n' \
  "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$SHALLOW_PATH" "$(printf '%s ' $SHALLOW_LIST)" "$GITDIR_ABS" "${GIT_NO_REPLACE_OBJECTS:-∅}"
NREP=$(printf '%s\n' $REPLACE_LIST | grep -c .)
[ "$NREP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] git replace -l 비공집합(${NREP}건: $(printf '%s ' $REPLACE_LIST)) — 부모 집합 재작성 = 신뢰 불가"
[ "$GRAFTS_PRESENT" = no ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED] $GRAFTS_PATH 실재 — 부모 집합 재작성 = 신뢰 불가 (GIT_NO_REPLACE_OBJECTS 로 무력화되지 않는다)"
show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  x-github-request-id=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "$(reqid "repos/$PIN_OR")" "${TARGET:-∅}"
{ ok2xx "$ST_APP" && [ -n "$APPID" ]; } || fire PREVENTION_UNVERIFIABLE "apps/github-actions 조회 실패(http=$ST_APP) — Actions app id 파생 불가"
{ ok2xx "$ST0" && [ -n "$TARGET" ]; }   || fire PREVENTION_UNVERIFIABLE "repos/$PIN_OR 조회 실패(http=$ST0) — default_branch 파생 불가"
[ -n "$MATCH_REMOTE" ] || fire PREVENTION_TARGET_MISMATCH "계약 핀 $CANON 과 일치하는 원격 부재 (git remote -v 정규화:${NORMED:- none})"

# ── 아티팩트 (전순서 2 ABSENT · 대조값·countersign)  — 커밋-전용 읽기
BODY=$(git show "HEAD:$PC" 2>/dev/null) || { fire PREVENTION_ABSENT "아티팩트 HEAD 부재: $PC"; BODY=""; }
yv() { printf '%s\n' "$BODY" | sed -n "s/^$1:[[:space:]]*//p" | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//' | head -1; }
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch)
CHECK="$GATE_JOB"   # [v2.22·F#2/N-4] 계약 리터럴 — «선언하지 않으면 고를 수 없다»(선례 gate_app_id·remote_name)
[ -z "$(yv tos_gate_check)" ] || printf 'U17-note 아티팩트에 tos_gate_check 키가 있으나 v2.22 는 폐지(무시) — 계약 리터럴 %s 사용\n' "$CHECK"
[ -z "$(yv gate_app_id)" ] || printf 'U17-note 아티팩트에 gate_app_id 키가 있으나 v2.18 은 폐지(무시) — 서버 파생값 %s 사용\n' "$APPID"
[ -z "$(yv remote_name)" ]  || printf 'U17-note 아티팩트에 remote_name 키가 있으나 v2.18 은 폐지(무시) — 핀 대조는 원격 이름을 묻지 않는다\n'
DECL_HOST=$(yv host)
if [ -n "$BODY" ]; then
  MM=""   # [E2] 선언 키는 «선택» — 있으면 대조, 없으면 핀·API 파생이 유일 소스
  if [ -n "$DECL_OR" ]; then case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=$DECL_OR ≠ 핀=$CANON)";; esac; fi
  if [ -n "$DECL_TB" ] && [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ]; then MM="$MM target_branch(선언=$DECL_TB ≠ 핀 repo default=$TARGET)"; fi
  # [E3] host 키도 «선택 대조» — 있으면 핀 host 와 대조, 없으면 핀이 유일 소스 (선언으로 host 를 «고를» 수 없다)
  if [ -n "$DECL_HOST" ] && [ "$DECL_HOST" != "$PIN_HOST" ]; then MM="$MM host(선언=$DECL_HOST ≠ 핀 host=$PIN_HOST)"; fi
  printf 'U17-T declared-vs-pin: %s (declared owner_repo=%s target_branch=%s host=%s)\n' "${MM:-일치/선언 없음}" "${DECL_OR:-∅(선택 키 부재 → 핀 유일 소스)}" "${DECL_TB:-∅(선택 키 부재 → default_branch 유일 소스)}" "${DECL_HOST:-∅(선택 키 부재 → 핀 host 유일 소스)}"
  [ -z "$MM" ] || fire PREVENTION_TARGET_MISMATCH "아티팩트 선언값이 계약 핀/파생값과 불일치:$MM"
  CS_RE='^operator_countersign:[[:space:]]*"[^"[:space:]][^"]* [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"[[:space:]]*(#.*)?$'
  nk=$(printf '%s\n' "$BODY" | grep -c '^operator_countersign:')
  if [ "$nk" != 1 ]; then fire PREVENTION_UNSIGNED "operator_countersign 키 출현 횟수=$nk (정확히 1 요구)"
  elif ! printf '%s\n' "$BODY" | grep -Eq "$CS_RE"; then fire PREVENTION_UNSIGNED "operator_countersign 값 형식 위반: $(printf '%s\n' "$BODY" | grep '^operator_countersign:')"; fi
fi

# ── (a) 4 엔드포인트 (핀 repo · 파생 target)
APPLIED_IDS=""
if [ -n "$TARGET" ]; then
P_PROT="repos/$PIN_OR/branches/$TARGET/protection"; P_RULES="repos/$PIN_OR/rules/branches/$TARGET"; P_RSETS="repos/$PIN_OR/rulesets"
respond "$P_PROT";  show_capture A1 "$P_PROT"
respond "$P_RULES"; show_capture A2 "$P_RULES"
respond "$P_RSETS"; show_capture A3 "$P_RSETS"
# [α] 연속성 입력우주 = target 에 «적용된» 룰셋만 (rules/branches/{target} 의 ruleset_id) — rulesets 목록 전체가 아니다
APPLIED_IDS=$(python3 -c 'import json,sys
ids=[]
try:
    a=json.load(open(sys.argv[1]))
    for r in a if isinstance(a,list) else []:
        if isinstance(r,dict) and r.get("ruleset_id") is not None and str(r["ruleset_id"]) not in ids: ids.append(str(r["ruleset_id"]))
except Exception: pass
print(" ".join(ids))' "$CAP/$(key "$P_RULES").body" 2>/dev/null)
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
for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; done
[ -n "$RSIDS" ] || printf 'U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)\n'
printf 'U17-α0 적용 룰셋(연속성 입력우주) = [%s]  (rules/branches/%s 의 ruleset_id · rulesets 목록 전체=[%s])\n' "$(printf '%s' "$APPLIED_IDS")" "$TARGET" "$(printf '%s' "$RSIDS")"
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

# ── [v2.22·M-7] (b-blob)@target — «D 무관 무조건 항» (계약 :5566-5591 · :5828-5849)
#    진입선(D=∅)에서도 «항상» 평가한다.  이것이 없으면 진입 판정이 blob 을 한 줄도 읽지 않는다(vacuity).
BT_STATE=NOT_EVALUATED
if [ -n "$TARGET" ]; then
  BQ="repos/$PIN_OR/branches/$TARGET"; respond "$BQ"; show_capture BT0 "$BQ"; BST=$(http_of "$BQ")
  if [ "$BST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target branches/$TARGET 네트워크/인증 오류"
  elif ! ok2xx "$BST"; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET http=$BST"
  else
    THSHA=$(jget "$BQ" commit.sha)
    printf 'U17-BT [M-7] target HEAD sha = %s   (계약 :5583 «verbatim 수록 필수» — 리뷰어 재조회 대조용)\n' "${THSHA:-∅(파생 불가)}"
    if [ -z "$THSHA" ]; then BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target branches/$TARGET 의 .commit.sha 파생 불가"
    else
      TQ="repos/$PIN_OR/contents/$WF_PATH?ref=$THSHA"; respond "$TQ"; show_capture BT1 "$TQ"; TST=$(http_of "$TQ")
      if [ "$TST" = ERR ]; then BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target contents 조회 네트워크/인증 오류 — $TQ"
      elif ! ok2xx "$TST"; then BT_STATE=UNVERIFIED_REVISION
        fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target http=$TST ($WF_PATH 가 target HEAD $THSHA 에 부재) — ABSENT 로 접지 않는다(전순서 2 vs 8)"
      else
        TWF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception: sys.stdout.write("")' "$CAP/$(key "$TQ").body")
        printf 'U17-BT1 decoded %s@%s (target HEAD · encoding=%s size=%s):\n' "$WF_PATH" "$THSHA" "$(jget "$TQ" encoding)" "$(jget "$TQ" size)"
        printf '%s\n' "$TWF" | sed 's/^/  | /'
        TWFF="$CAP/$(key "$TQ").wf.yml"; printf '%s\n' "$TWF" > "$TWFF"
        TOUT=$("$PYBIN" "$WFCANON" blob "$TWFF" 2>&1)
        printf '%s\n' "$TOUT" | sed 's/^/  | /'
        TRES=$(printf '%s\n' "$TOUT" | sed -n 's/^RESULT=//p' | tail -1)
        case "$TRES" in
          BLOB_OK) BT_STATE=OK ;;
          UNVERIFIABLE) BT_STATE=UNVERIFIABLE; fire PREVENTION_UNVERIFIABLE "(b-blob)@target 정본 잡 대조 불가(파서 핀 불일치·YAML 파서 실패)" ;;
          *) BT_STATE=UNVERIFIED_REVISION; fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@target 정본 잡 템플릿 불일치 (target HEAD=$THSHA · T-84 ⑬)" ;;
        esac
      fi
    fi
  fi
else
  printf 'U17-BT [M-7] target 미파생 — (b-blob)@target 평가 불가 (전순서 1 이 이미 발화)\n'
fi
printf 'U17-BT (b-blob)@target 판정 = %s   [무조건 항 · D 와 무관]\n' "$BT_STATE"

# ── (c) P_first / P_last · D  (구조 정의 · 후보 = --full-history)
# [SHALLOW/E5] 후보 우주 안에 «경계 커밋»이 있으면 그 x 를 도입 지점으로 «확정하지 않는다».
# 함수는 «명령 치환 서브셸»에서 돌므로 변수로 되돌릴 수 없다 — 경계 목록은 파일로 넘긴다.
BNDF=$(mktemp); BND_D=""; BND_P=""
intro_set() { local path="$1" out="" x p intro; : > "$BNDF"; for x in $(git rev-list --full-history HEAD -- "$path"); do git cat-file -e "$x:$path" 2>/dev/null || continue
    check_parents "$x" || true
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    intro=1; for p in $(parents_true "$x"); do git cat-file -e "$p:$path" 2>/dev/null && { intro=0; break; }; done; [ "$intro" = 1 ] && out="$out $x"; done; printf '%s' "$out"; }
# [E9] P_last = «현행 blob 의 도입 지점 집합»(C_R 동형 · ∀-부모).  ∨(«어느 한 부모와라도 다름») 폐기.
blob_intro_set() { local path="$1" b="$2" out="" x p same; : > "$BNDF"
  for x in $(git rev-list --full-history HEAD -- "$path"); do
    [ "$(git rev-parse -q --verify "$x:$path" 2>/dev/null || echo ABSENT)" = "$b" ] || continue
    check_parents "$x" || true
    if is_boundary "$x"; then printf '%s\n' "$x" >> "$BNDF"; continue; fi
    same=0; for p in $(parents_true "$x"); do
      [ "$(git rev-parse -q --verify "$p:$path" 2>/dev/null || echo ABSENT)" = "$b" ] && { same=1; break; }; done
    [ "$same" = 0 ] && out="$out $x"; done; printf '%s' "$out"; }
if [ -n "$BODY" ]; then
  P_FIRST_SET=$(intro_set "$PC"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
  HEAD_BLOB=$(git rev-parse "HEAD:$PC")
  P_LAST_SET=$(blob_intro_set "$PC" "$HEAD_BLOB"); BND_P="$BND_P $(tr '\n' ' ' < "$BNDF")"
else P_FIRST_SET=""; P_LAST_SET=""; HEAD_BLOB=""; fi
NPF=$(printf '%s\n' $P_FIRST_SET | grep -c .); NPL=$(printf '%s\n' $P_LAST_SET | grep -c .)
D=$(intro_set "$CFG"); BND_D=$(tr '\n' ' ' < "$BNDF"); ND=$(printf '%s\n' $D | grep -c .)
printf 'P_first(집합·|%s|)=[%s] P_last(집합·|%s|·blob=%s)=[%s] |D|=%s D=[%s]  [E9 ∀-부모]\n' \
  "$NPF" "$(printf '%s ' $P_FIRST_SET)" "$NPL" "${HEAD_BLOB:-∅}" "$(printf '%s ' $P_LAST_SET)" "$ND" "$(printf '%s ' $D)"
BND_D=$(printf '%s\n' $BND_D | sort -u | tr '\n' ' '); BND_P=$(printf '%s\n' $BND_P | sort -u | tr '\n' ' ')
# [E10 ㉠] 후보 전수에 대해 «재파생 vs 이력 뷰» 대조 결과를 방출하고 불일치는 전역 차단
PU_CHECKED=$(sort -u "$PUC" | grep -c .); PU_N=$(grep -c . "$PUF"); PU_MISMATCH=$(tr '\n' ' ' < "$PUF")
PU_L=$(grep -c . "$PUL")
printf 'U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 %s건=[%s]\n' "$PU_L" "$(tr '\n' ' ' < "$PUL")"
printf 'U17-PU㉠ 재파생 대조: 검사 후보 %s건 · «남는» 전역 불일치 %s건=[%s]\n' "$PU_CHECKED" "$PU_N" "$PU_MISMATCH"
[ "$PU_N" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[PARENTS-UNTRUSTED ㉠] 부모 재파생 ≠ 이력 뷰 — 이력 뷰가 재작성됨: $PU_MISMATCH"
NBD=$(printf '%s\n' $BND_D | grep -c .); NBP=$(printf '%s\n' $BND_P | grep -c .)
printf 'U17-SHALLOW is_shallow=%s shallow 목록(%s)=[%s] · 후보 우주 내 경계 커밋: D=[%s](%s건) P=[%s](%s건)  (E6: 전역 단축 아님 — 경로별 국소 판정)\n' "$IS_SHALLOW" "$SHALLOW_PATH" "$(printf '%s ' $SHALLOW_LIST)" "$(printf '%s ' $BND_D)" "$NBD" "$(printf '%s ' $BND_P)" "$NBP"
[ "$NBD" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] D 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_D)) — 부모 미상이라 도입 지점 확정 불가 (부재를 «참»으로 접지 않는다)"
[ "$NBP" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[SHALLOW] P_first/P_last 후보 우주에 얕은 클론 경계 커밋($(printf '%s ' $BND_P)) — 확정 불가"
sanc() { git merge-base --is-ancestor "$1" "$2" 2>/dev/null && [ "$1" != "$2" ]; }   # 진(strict) 조상
if [ -n "$BODY" ]; then
  # [E9] 카디널리티 처분은 «무조건 항»(c_APP 동형) — |P_last|=0 은 이력 파생 실패다
  [ "$NPL" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E9] |P_last|=0 — 현행 blob($HEAD_BLOB)의 도입 지점 없음 = 이력 파생 실패/[PARENTS-UNTRUSTED]"
  # [E11] P_first 카디널리티 — 아티팩트가 «존재»하는데 도입 지점이 ∅ 이면 [PARENTS-UNTRUSTED] 로 확정 불가
  [ "$NPF" -ne 0 ] || fire PREVENTION_UNVERIFIABLE "[E11] 아티팩트는 HEAD 에 «존재»하나 |P_first|=0 — [PARENTS-UNTRUSTED](㉢ 경계/㉠ 재작성)로 경로 도입 지점 확정 불가"
fi
# [E11] 아티팩트 «부재» 이면 |P_first|=0 이 정상이며 전순서 2 ABSENT 가 이미 발화했다(위 아티팩트 절) — 여기서 재발화하지 않는다
if [ -n "$BODY" ] && [ "$ND" -gt 0 ]; then
  LATE=0
  for d in $D; do hit=0; for x in $P_FIRST_SET; do sanc "$x" "$d" && { hit=1; break; }; done; [ "$hit" = 1 ] || LATE=1; done
  if [ "$LATE" = 1 ]; then fire PREVENTION_LATE "[E9] ∃d∈D: ∀x∈P_first(|$NPF|) x ⋠ d — 그 착지 시점에 경로가 없었다"
  else
    if [ "$NPL" -gt 1 ]; then fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ |P_last|=$NPL>1 ($(printf '%s ' $P_LAST_SET)) — 현행 내용의 도입 지점이 유일하지 않다"
    elif [ "$NPL" -eq 1 ]; then X_LAST=$(printf '%s' $P_LAST_SET); MUT=0
      for d in $D; do sanc "$X_LAST" "$d" || MUT=1; done
      [ "$MUT" = 0 ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] ¬LATE ∧ ∃d∈D: x_last=$X_LAST ⋠ d — 착수 «후» 아티팩트 변경"
      [ "$(git rev-parse "HEAD:$PC")" = "$(git rev-parse "$X_LAST:$PC")" ] || fire PREVENTION_ARTIFACT_MUTATED "[E9] 소비 blob(HEAD) ≠ blob(x_last)"
    fi
  fi
fi

# ── (b) 리비전 특정 ∀d∈D (전순서 8) — D=∅ 는 «검증 대상 없음»(명시)
MINMERGED=""
if [ "$ND" -eq 0 ]; then
  printf 'U17-B D=∅ — (b-blob)@d·(b-server)·(c) 는 «D-지표 항»이라 평가 대상 없음.  **(b-blob)@target 은 위에서 «무조건 항»으로 이미 평가됐다**(v2.22·M-7 — v2.21 은 (b)(c) 를 통째로 접었다·심판 #3 vacuity)\n'
elif [ -n "$TARGET" ]; then
  for d in $D; do
    # ══ [레인1] (b)① pulls — 열거 규율 적용 (bare array · limb ② 정의역)
    PLP="repos/$PIN_OR/commits/$d/pulls?per_page=100"
    respond "$PLP"; show_capture B1 "$PLP"; PST=$(http_of "$PLP")
    if [ "$PST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls 조회 네트워크/인증 오류 — $PLP"; continue
    elif ! ok2xx "$PST"; then fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls http=$PST — $PLP"; continue; fi
    PK="$CAP/$(key "$PLP")"
    respond_slurp "$PLP"; show_slurp "$PLP"; PSL=$(cat "$PK.slurp.status" 2>/dev/null)
    if ! ok2xx "$PSL"; then fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls --slurp 조회 실패(status=${PSL:-∅}) — 페이지 수 N 관측 불가"; continue; fi
    PNP=$(python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1])); print(len(j) if isinstance(j,list) else "")
except Exception: print("")' "$PK.slurp.body")
    [ -n "$PNP" ] || { fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls --slurp 본문이 «페이지 배열의 배열»이 아니다"; continue; }
    PTP="$PLP&page=$((PNP+1))"; respond "$PTP"; show_capture B1t "$PTP"; PTS=$(http_of "$PTP")
    if [ "$PTS" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls 종단 프로브 네트워크/인증 오류 — $PTP"; continue
    elif ! ok2xx "$PTS"; then fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls 종단 프로브 http=$PTS — $PTP"; continue; fi
    PPOUT=$("$PYBIN" "$PAGELIMB" "$PAGE_MODE" "$PK.body" "$PK.hdr" "$PK.slurp.body" "$CAP/$(key "$PTP").body" NONE "$PK.collected.json" 2>&1); PPRC=$?
    printf '%s
' "$PPOUT" | sed 's/^/  | /'
    PPRES=$(printf '%s
' "$PPOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$PPRES" in PAGES_OK\|*) : ;;
      *) fire PREVENTION_UNVERIFIABLE "(b)① d=$d pulls 열거 완전성 불충족 — ${PPRES#*|}"; continue ;; esac
    HS=$(python3 - "$PK.collected.json" "$TARGET" <<'PYX'
import json,sys
prs=json.load(open(sys.argv[1])); target=sys.argv[2]
if not isinstance(prs,list): print("UNVERIFIABLE|pulls 수집 결과가 배열이 아니다"); sys.exit(0)
ok=[p for p in prs if isinstance(p,dict) and p.get("merged_at") and (p.get("base") or {}).get("ref")==target]
if not ok: print("UNVERIFIED_REVISION|착지 PR 부재·merged 아님·base≠target (pulls=%d)"%len(prs)); sys.exit(0)
print("HEAD|%s|%s"%(ok[0]["head"]["sha"],ok[0]["merged_at"]))
PYX
)
    case "$HS" in UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b) d=$d ${HS#*|}"; continue ;; UNVERIFIED_REVISION\|*) fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d ${HS#*|}"; continue ;; esac
    HSHA=$(printf '%s' "$HS" | cut -d'|' -f2); MERGED=$(printf '%s' "$HS" | cut -d'|' -f3); { [ -z "$MINMERGED" ] || [[ "$MERGED" < "$MINMERGED" ]]; } && MINMERGED="$MERGED"
    # ══ [레인1] (b)② 재작성 — 열거 규율(ⓛ/2차ⓡ/5차ⓧ) + 4단 사다리(3차ⓣ/4차ⓥ/5차ⓦ)
    #    판정 논리는 «술어 파일»에 있고 이 블록은 조회·결속 해석·transcript 만 한다.
    CRP="repos/$PIN_OR/commits/$HSHA/check-runs?filter=all&per_page=100"   # filter=all(2차ⓞㄱ) + per_page=100(계약 리터럴)
    respond "$CRP"; show_capture B2 "$CRP"; CRST=$(http_of "$CRP")
    if [ "$CRST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② d=$d check-runs 조회 네트워크/인증 오류 — $CRP"; continue
    elif ! ok2xx "$CRST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA check-runs http=$CRST — 열거 실패(검사 생략 금지)"; continue; fi
    CK="$CAP/$(key "$CRP")"
    respond_slurp "$CRP"; show_slurp "$CRP"; SLST=$(cat "$CK.slurp.status" 2>/dev/null)
    if ! ok2xx "$SLST"; then fire PREVENTION_UNVERIFIABLE "(b)② d=$d --slurp 조회 실패(status=${SLST:-∅}) — 페이지 수 N 을 본문에서 관측 불가"; continue; fi
    NPG=$(python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1])); print(len(j) if isinstance(j,list) else "")
except Exception: print("")' "$CK.slurp.body")
    [ -n "$NPG" ] || { fire PREVENTION_UNVERIFIABLE "(b)② d=$d --slurp 본문이 «페이지 배열의 배열»이 아니다 — 열거 완전성 관측 불가"; continue; }
    # 종단 프로브 — `filter=all` 을 «그대로» 이어 붙인다.  이 핀을 빼면 열거와 프로브가
    #   «서로 다른 컬렉션»을 보게 되므로, 계약 문언 `?page=<N+1>&per_page=100` 의 이 자리 이행이다.
    TRP="$CRP&page=$((NPG+1))"
    respond "$TRP"; show_capture B2t "$TRP"; TRST=$(http_of "$TRP")
    if [ "$TRST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② d=$d 종단 프로브 네트워크/인증 오류 — $TRP"; continue
    elif ! ok2xx "$TRST"; then fire PREVENTION_UNVERIFIABLE "(b)② d=$d 종단 프로브 http=$TRST — 열거 완전성 관측 불가 — $TRP"; continue; fi
    PLOUT=$("$PYBIN" "$PAGELIMB" "$PAGE_MODE" "$CK.body" "$CK.hdr" "$CK.slurp.body" "$CAP/$(key "$TRP").body" check_runs "$CK.collected.json" 2>&1); PLRC=$?
    printf '%s\n' "$PLOUT" | sed 's/^/  | /'
    PLRES=$(printf '%s\n' "$PLOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$PLRES" in PAGES_OK\|*) : ;;
      *) fire PREVENTION_UNVERIFIABLE "(b)② d=$d head=$HSHA 열거 완전성 불충족 — ${PLRES#*|}"; continue ;; esac
    # ── run 결속 해석 — 동명 check-run 마다 workflow run(path·head_sha)을 조회해 사다리에 넘긴다
    NAMED=$(python3 - "$CK.collected.json" "$CHECK" <<'PY'
import json,sys,re
els=json.load(open(sys.argv[1])); chk=sys.argv[2]
for i,cr in enumerate(els):
    if not isinstance(cr,dict) or cr.get("name")!=chk: continue
    rid=""
    for u in (cr.get("details_url") or "", cr.get("html_url") or ""):
        m=re.search(r"/actions/runs/(\d+)",u)
        if m: rid=m.group(1); break
    print("CR|%d|%s|%s"%(i,(cr.get("check_suite") or {}).get("id"),rid))
PY
)
    RESL="$CK.runs.tsv"; : > "$RESL"; RESBAD=0
    while IFS='|' read -r tag idx sid rid; do
      [ "$tag" = CR ] || continue
      if [ -z "$rid" ]; then
        Q="repos/$PIN_OR/actions/runs?check_suite_id=$sid&per_page=100"; respond "$Q"; show_capture B4q "$Q"; QST=$(http_of "$Q")
        if [ "$QST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $Q 네트워크/인증 오류"; RESBAD=1; continue
        elif ! ok2xx "$QST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)② check-run #$idx → suite $sid http=$QST"; RESBAD=1; continue; fi
        SR=$(python3 - "$CAP/$(key "$Q").body" <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); r=j.get("workflow_runs") or []
print("ONE|%s"%r[0].get("id") if len(r)==1 else "AMBIG|%d"%len(r))
PY
)
        case "$SR" in ONE\|*) rid="${SR#ONE|}" ;;
          *) fire PREVENTION_UNVERIFIED_REVISION "(b)② check-run #$idx: details_url 에 run id 부재 ∧ suite $sid 안 run ${SR#AMBIG|}개 = 모호 → 결속 불가(fail-closed)"; RESBAD=1; continue ;; esac
      fi
      RQ="repos/$PIN_OR/actions/runs/$rid"; respond "$RQ"; show_capture B4 "$RQ"; RST=$(http_of "$RQ")
      if [ "$RST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $RQ 네트워크/인증 오류"; RESBAD=1; continue
      elif ! ok2xx "$RST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)② check-run #$idx → runs/$rid http=$RST"; RESBAD=1; continue; fi
      RPATH=$(jget "$RQ" path); RHEAD=$(jget "$RQ" head_sha)
      printf '%s\t%s\t%s\t%s\t%s\n' "$idx" "$rid" "$RPATH" "$RHEAD" "$sid" >> "$RESL"
      # [E2] 정본 path 원소만 check_suite 귀속 일치를 요구한다 (v2.22 원문 거동 유지 — 코드 델타 0 축)
      if [ "$RPATH" = "$WF_PATH" ]; then
        SQ="repos/$PIN_OR/check-suites/$sid"; respond "$SQ"; show_capture B3 "$SQ"; SST=$(http_of "$SQ")
        if [ "$SST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)② $SQ 네트워크/인증 오류"; RESBAD=1
        elif ! ok2xx "$SST"; then fire PREVENTION_UNVERIFIABLE "(b)② $SQ http=$SST"; RESBAD=1
        elif [ "$(jget "$SQ" head_sha)" != "$HSHA" ]; then fire PREVENTION_UNVERIFIED_REVISION "(b)② suite $sid head_sha≠PR head"; RESBAD=1; fi
      fi
    done <<< "$NAMED"
    [ "$RESBAD" = 0 ] || continue
    RUNSJ="$CK.runs.json"
    python3 - "$RESL" "$RUNSJ" <<'PY'
import json,sys
out={}
for l in open(sys.argv[1]):
    p=l.rstrip("\n").split("\t")
    if len(p)<5: continue
    out[p[1]]={"path":p[2],"head_sha":p[3],"check_suite_id":p[4]}
json.dump(out,open(sys.argv[2],"w"))
PY
    printf 'U17-B2r run 결속 해석 (idx / run / path / run.head_sha / suite) — %s행:\n' "$(grep -c . "$RESL" 2>/dev/null || echo 0)"; sed 's/^/  | /' "$RESL"
    LADOUT=$("$PYBIN" "$LADDER" "$CK.collected.json" "$RUNSJ" "$CHECK" "$WF_PATH" "$HSHA" "$APPID" 2>&1); LADRC=$?
    printf '%s\n' "$LADOUT" | sed 's/^/  | /'
    LADRES=$(printf '%s\n' "$LADOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$LADRES" in
      LADDER_OK\|*) : ;;
      PREVENTION_UNVERIFIABLE\|*) fire PREVENTION_UNVERIFIABLE "(b)② d=$d head=$HSHA ${LADRES#*|}"; continue ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b)② d=$d head=$HSHA ${LADRES#*|}"; continue ;;
    esac
    R_SET=$(printf '%s\n' "$LADOUT" | sed -n 's/^LAD-R //p' | tr '\n' ' ')
    printf 'U17-B2R 층 ① 과 층 (2) 가 소비하는 R = { %s} — 사다리 3단계 «현행» 집합에서 파생(2차 ⓝ·5차 ⓦ)\n' "$R_SET"
    # [R2-③·E1] 그 head_sha 시점의 워크플로 blob — «서버»에서 읽는다: contents/<path>?ref=<head> → base64 decode → 두 리터럴 grep
    CQ="repos/$PIN_OR/contents/$WF_PATH?ref=$HSHA"; respond "$CQ"; show_capture B5 "$CQ"; CST=$(http_of "$CQ")
    if [ "$CST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b) d=$d head=$HSHA contents 조회 네트워크/인증 오류 — $CQ"; continue
    elif ! ok2xx "$CST"; then fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA contents http=$CST ($WF_PATH 부재·조회 실패) — 검사 생략 금지"; continue; fi
    WF=$(python3 -c 'import json,sys,base64
try:
    j=json.load(open(sys.argv[1])); enc=j.get("encoding"); c=j.get("content","")
    sys.stdout.write(base64.b64decode(c).decode("utf-8","replace") if enc=="base64" else str(c))
except Exception as e: sys.stdout.write("")' "$CAP/$(key "$CQ").body")
    printf 'U17-B5 decoded %s@%s (encoding=%s size=%s):\n' "$WF_PATH" "$HSHA" "$(jget "$CQ" encoding)" "$(jget "$CQ" size)"; printf '%s\n' "$WF" | sed 's/^/  | /'
    # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
    WFF="$CAP/$(key "$CQ").wf.yml"; printf '%s\n' "$WF" > "$WFF"
    WFOUT=$("$PYBIN" "$WFCANON" blob "$WFF" 2>&1); WFRC=$?   # [v2.22·F#2] 계약 리터럴은 술어 «안»에 있다 — env 로 선언하지 않는다(자기선택 표면 제거)
    printf '%s\n' "$WFOUT" | sed 's/^/  | /'
    WFRES=$(printf '%s\n' "$WFOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$WFRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b-blob)@d d=$d head=$HSHA 정본 잡 대조 불가(파서 핀 `yq (mikefarah) v4.48.x` 불일치 또는 YAML 파서 실패 — M-4)"; continue ;;
      BLOB_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b-blob)@d d=$d head=$HSHA 정본 «잡 템플릿» 불일치 — 최상위 allowlist·jobs 개수·잡 키/name/runs-on·steps 순서·체크아웃 with·스텝 메타·중복 키 중 하나 이상 (T-84 ⑬)"; continue ;;
    esac
    # ── [v2.20 #1 (2)] 서버 잡 스텝 대조 — actions/runs/{run_id}/jobs (계약 리터럴 스텝 이름 × conclusion)
    # ══ [레인1 · 2차 ⓝ] 층 (2) 서버 잡 스텝 대조 — **∀ r ∈ R** (run-스코프)
    #    run 간 «합산» 금지(합치면 정직한 2-run 구성이 `len(hit)=2` 로 red) · «선택» 금지(선택 규칙은
    #    계약이 사다리 3단계에서 핀한다).  `hit_r` 유일성·잡 conclusion·두 스텝은 술어 파일 소관.
    [ -n "${R_SET// /}" ] || { fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA R=∅ — 서버 스텝 대조 불가"; continue; }
    JBAD=0
    for r in $R_SET; do
      printf 'U17-B6a r=%s run_attempt=%s (ⓓ — 어느 attempt 를 본 판정인지 병기)\n' "$r" "$(jget "repos/$PIN_OR/actions/runs/$r" run_attempt)"
      JQ="repos/$PIN_OR/actions/runs/$r/jobs?filter=latest&per_page=100"   # filter=latest 핀(ⓓ) + per_page=100
      respond "$JQ"; show_capture B6 "$JQ"; JST=$(http_of "$JQ")
      if [ "$JST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)③ d=$d r=$r jobs 조회 네트워크/인증 오류 — $JQ"; JBAD=1; continue
      elif ! ok2xx "$JST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d r=$r jobs http=$JST — 서버 스텝 기록 조회 실패(검사 생략 금지)"; JBAD=1; continue; fi
      SVOUT=$("$PYBIN" "$WFCANON" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?
      printf '%s\n' "$SVOUT" | sed 's/^/  | /'
      SVRES=$(printf '%s\n' "$SVOUT" | sed -n 's/^RESULT=//p' | tail -1)
      case "$SVRES" in
        UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d r=$r jobs 본문 파싱 실패"; JBAD=1 ;;
        SERVER_OK) : ;;
        *) fire PREVENTION_UNVERIFIED_REVISION "(b-server) d=$d head=$HSHA r=$r 서버 대조 실패 — 이름 필터 hit_r 비-유일(len≠1) · 잡 conclusion≠\"success\" · 계약 리터럴 스텝 이름 부재/비-success (T-84 ⑭)"; JBAD=1 ;;
      esac
    done
    [ "$JBAD" = 0 ] || continue
    if git cat-file -e "$HSHA^{commit}" 2>/dev/null; then LB=$(git rev-parse -q --verify "$HSHA:$WF_PATH" 2>/dev/null || echo ABSENT); printf 'U17-B5x 보조(선택·판정 미소비): 로컬 git show %s:%s → %s\n' "$HSHA" "$WF_PATH" "$LB"; else printf 'U17-B5x 보조(선택·판정 미소비): 로컬에 %s 커밋 없음 — 서버 조회만으로 판정\n' "$HSHA"; fi
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
  done
fi

# ── (α) [v2.19 — 심판 F1] 연속성 소비자 (전순서 9) — «서버 시간»만 소비한다
if [ "$ND" -eq 0 ]; then
  printf 'U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)\n'
elif [ -z "$TARGET" ]; then
  printf 'U17-α target 미파생 — 연속성 평가 불가 (전순서 1 이 이미 발화)\n'
elif [ -z "$MINMERGED" ]; then
  fire PREVENTION_CONTINUITY_UNVERIFIABLE "t_land 파생 불가(D≠∅ 이나 착지 PR 의 서버 merged_at 미해석) — 연속성 판정 불가"
else
  printf 'U17-α t_land = min{merged_at(착지 PR) : d∈D} = %s  (서버 부여 값만 · 커밋 author/committer date 불신)\n' "$MINMERGED"
  if [ -z "$APPLIED_IDS" ]; then
    fire PREVENTION_CONTINUITY_UNVERIFIABLE "적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가"
  else
    for id in $APPLIED_IDS; do
      CA=$(jget "repos/$PIN_OR/rulesets/$id" created_at); UA=$(jget "repos/$PIN_OR/rulesets/$id" updated_at)
      CONT=$(python3 - "$id" "$CA" "$UA" "$MINMERGED" <<'PY'
import sys,datetime
i,ca,ua,mm=sys.argv[1:5]
def p(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(datetime.timezone.utc)
    except Exception: return None
c,u,m=p(ca),p(ua),p(mm)
if m is None: print("BLOCK|t_land 파싱 불가(merged_at=%s)"%mm); sys.exit(0)
if c is None or u is None: print("BLOCK|ruleset %s 서버 타임스탬프 부재·파싱 불가(created_at=%s updated_at=%s) — 연속성 판정 불가"%(i,ca,ua)); sys.exit(0)
if c>m: print("BLOCK|ruleset %s created_at=%s > t_land=%s — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호"%(i,c.isoformat(),m.isoformat())); sys.exit(0)
if u>m: print("BLOCK|ruleset %s updated_at=%s > t_land=%s — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가"%(i,u.isoformat(),m.isoformat())); sys.exit(0)
print("PASS|ruleset %s created_at=%s ≤ t_land ∧ updated_at=%s ≤ t_land"%(i,c.isoformat(),u.isoformat()))
PY
)
      printf 'U17-α ruleset %s: %s\n' "$id" "${CONT#*|}"
      case "$CONT" in BLOCK\|*) fire PREVENTION_CONTINUITY_UNVERIFIABLE "(α) ${CONT#*|} — 운영자 재심사 경로(영구 차단 아님)";; esac
    done
  fi
fi

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ **(b-blob)@target=$BT_STATE(무조건 항·target HEAD=${THSHA:-∅})** ∧ (b-blob)@d·(b-server) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
