# U17-PREVENTION-CHECK-V220 — T-84 실행 증거 (계약 v2.20 동결 `3d17ea66` · 구조 워크플로 검증 + 서버 스텝 대조)

- **비규범 부속**(non-normative). 계약·개발계획을 바꾸지 않는다. 판정 권한 없음 — 실행 «기록»이다.
- 생성 UTC: `2026-08-19T07:57:23Z` (드라이버 첫 줄 원문)
- **S-24 결속**(§1 원문): HEAD == `3d17ea66` · 계약 워킹트리 blob == `git show 3d17ea66:` blob · 개발계획 blob == 동결 blob · `3d17ea66..HEAD` 두 문서 커밋 **0** · 하니스 `sed -n '4654,4754p'` sha256 == `957bf49d…` **byte-동일**
- 실행기: `u17-verify-v220.sh` sha256 `67d636ce4ac4ff0b4a3da06d24b5551748c7408d3325aebd9f5ac56b264ed101` (481행) · 구조 파싱 술어 `wfstruct-v220.py` sha256 `792aaa1e73d8ef854c7478577b0732191065b961802f5988687cc03299760dc1` (251행) — v2.19 에라타 6차 실행기(`174b0c18…`)에서 **파생**(델타 §2)
- **GitHub 는 GET-only** — `gh api -i --hostname github.com <GET path>` 조회뿐. **서버 쓰기·설정 변경 0**(POST/PATCH/PUT/DELETE 0). 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용).
- **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다** — 아래 서버 파생 실측은 `x-github-request-id` 와 함께 원문으로 남긴다(§7).

## 1. S-24 결속 원문

```text
s24_v220_utc=2026-08-19T07:51:32Z
① HEAD          = 3d17ea66896062140679faa895463b13a65cd510   (동결 3d17ea66 과 동일? YES)
② 계약 워킹트리 blob = 5d6044e904e9c2e74bf4abb661b3b4b47f044689
   계약 동결 blob      = 5d6044e904e9c2e74bf4abb661b3b4b47f044689   → 동일
③ 개발계획 워킹트리 blob = d00aa15ef84a9f76058403a0dd91549c9f614533
   개발계획 동결 blob      = d00aa15ef84a9f76058403a0dd91549c9f614533   → 동일
④ 3d17ea66..HEAD 두 문서 커밋 = 0건
   3d17ea66..HEAD 전체 커밋   = 0건
⑤ 계약 행수 = 7494 · 개발계획 행수 = 579
⑥ 하니스 §12.3.4-R 블록 (계약 :4654-4754 · 101행) sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
   계약 리터럴                                   = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   → 일치
   블록 경계 원문: #!/usr/bin/env bash
                   emit ENTRY_OK "R-0~R-7 전부 기대와 일치"
⑦ 동결 blob 에서 같은 범위 추출 → sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (byte-동일? YES)
⑧ 워킹트리 상태 (두 문서 한정): 0건 변경
⑨ 본 저장소 [PARENTS-UNTRUSTED] 관측: git replace -l=[] · info/grafts=ABSENT · is_shallow=false
⑩ 픽스처 격리: 본 저장소 밖 독립 저장소 = 9개 · worktree = 3 (본 저장소 worktree 목록)
```

## 2. 실행기 파생 — v2.19 에라타 6차 → v2.20 (델타 3건)

| 델타 | 계약 근거 | 내용 |
| --- | --- | --- |
| **D-α** | `(b)③` :5452-5486 (#1) | «두 리터럴 grep» → **구조 YAML 파싱**(`jobs.<게이트 잡>.steps[]` 의 `run:` «실행문만» · 셸 토크나이즈 · `#` 주석[full-line·trailing] 제거 · `bash -n` 파스) |
| **D-β** | `(b)③(2)` :5478-5486 (#1) | **서버 잡 스텝 대조** — `actions/runs/{run_id}/jobs` 의 그 잡 `conclusion==success` ∧ 계약 리터럴 두 «스텝 이름»이 각각 `conclusion==success` (부재·실패 → `UNVERIFIED_REVISION` · T-84 ⑭). `run_id` 는 `actions/runs?check_suite_id` 응답에서 **구조 파생** |
| **D-γ** | :7098-7124 (#3) | **격리 스냅샷 기층** — 조상성·부모·blob 소비를 진입 시점 HEAD 스냅샷 «안에서만». 부수로 `gitpath()` 결합 base 를 **호출 시점 파생**으로 교체(스냅샷 진입 후 캐시된 base 는 «거짓 ABSENT» = E15 극성 재발 — §9 M-1) |

```diff
2c2,12
< # u17-verify (v2.19 에라타 6차 359f5bc5) — U-17 «예방 통제 활성 증거» 실행기 (계약 359f5bc5 §12.3.4 U-17)
---
> # u17-verify (v2.20 동결 3d17ea66) — U-17 «예방 통제 활성 증거» 실행기 (계약 3d17ea66 §12.3.4 U-17)
> #   v2.19 에라타 6차 실행기(359f5bc5·sha256 174b0c18...) 에서 파생 — 델타는 **v2.20 심판 처분 2건**뿐이다:
> #     [#1 — (b)3 :5452-5486] «두 리터럴 grep» -> **구조 파싱 + 서버 스텝 대조** 2층.
> #           (1) 서버 blob 을 YAML 파서로 구조 파싱해 jobs.<게이트 잡>.steps[] 의 run: «실행문만» 소비
> #               (셸 토크나이즈·# 주석[full-line·trailing] 제거·bash -n 파스 — wfstruct-v220.py)
> #           (2) actions/runs/{run_id}/jobs 의 그 잡 conclusion==success 이고 계약 리터럴 두 «스텝 이름»이
> #               각각 conclusion==success 로 실재 — 부재·실패 -> PREVENTION_UNVERIFIED_REVISION (T-84 14)
> #     [#3 — [PARENTS-UNTRUSTED] :7098-7124] **격리 스냅샷 기층** — 조상성·부모·blob 소비를 진입 시점 HEAD 의
> #           git clone --no-local --no-hardlinks (+GIT_NO_REPLACE_OBJECTS=1) 스냅샷 «안에서만» 수행하고,
> #           스냅샷 청정성(제2 공집합·grafts 부재·제1 일치)을 canary 로 방출한다.  clone 실패는 **fail-closed**.
> #           원 저장소 관측은 «리뷰 보조»로 격하돼 기록만 남는다.
19a30
> WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfstruct-v220.py}"   # [v2.20 #1] 구조 파싱 술어 (YAML 파서·셸 토크나이저)
71c82,84
< gitpath() { local v; v=$(git rev-parse --git-path "$1" 2>/dev/null); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$TOPLEVEL" "$v";; esac; }
---
> # [v2.20 D-γ] 결합 base 를 «호출 시점»에 파생한다 — 격리 스냅샷으로 cwd 가 바뀐 뒤 캐시된 TOPLEVEL 을 쓰면
> #   스냅샷의 grafts 를 «원 저장소 경로»로 검사해 «거짓 ABSENT» 가 된다(E15 극성 규율의 재발 표면).
> gitpath() { local v t; v=$(git rev-parse --git-path "$1" 2>/dev/null); t=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s' "$TOPLEVEL"); case "$v" in /*) printf '%s' "$v";; "") printf '';; *) printf '%s/%s' "$t" "$v";; esac; }
102a116,141
> # ── [v2.20 — 심판 #3] 격리 스냅샷 기층 (계약 3d17ea66 :7098-7124) ─────────────────────────────
> #   조상성·부모·blob 을 소비하는 «모든» 판정을 진입 시점 HEAD 의 격리 스냅샷 «안에서만» 수행한다.
> #   원격 관측(위 [C3])은 원 저장소 «설정»이라 스냅샷 «전»에 끝내고, 아래부터는 스냅샷이 기층이다.
> ORIGIN=$(pwd -P); ENTRY_HEAD=$(git rev-parse HEAD 2>/dev/null || printf '')
> printf 'U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[%s] · %s=%s · is_shallow=%s · entry HEAD=%s\n' \
>   "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "${ENTRY_HEAD:-∅}"
> [ -n "$ENTRY_HEAD" ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 시점 HEAD 파생 불가"
> SNAPBASE=$(mktemp -d); SNAP="$SNAPBASE/snap"
> printf 'U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks %s %s\n' "$ORIGIN" "$SNAP"
> GIT_NO_REPLACE_OBJECTS=1 git clone --quiet --no-local --no-hardlinks "$ORIGIN" "$SNAP" 2>"$CAP/clone.err"; CRC=$?
> printf 'U17-SNAP clone rc=%s\n' "$CRC"; [ -s "$CAP/clone.err" ] && sed 's/^/  | /' "$CAP/clone.err"
> [ "$CRC" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] clone 실패(rc=$CRC) — 정직 경계 (a): 원본 grafts 가 참 부모를 도달 불가로 만들면 스냅샷 «생성»이 실패한다(거짓 통과 없음·fail-closed)"
> git -C "$SNAP" cat-file -e "$ENTRY_HEAD^{commit}" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD($ENTRY_HEAD) 가 스냅샷에 부재 — 핀 실패 fail-closed"
> git -C "$SNAP" checkout --quiet --detach "$ENTRY_HEAD" 2>/dev/null || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 진입 HEAD 체크아웃 실패"
> cd "$SNAP" || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷] 스냅샷 진입 실패"
> # ㉠㉡㉢ 는 스냅샷 «안에서» 재파생한다 (계약: 스냅샷 안 ㉡ = 기층이 깨끗함을 고정하는 canary)
> SHALLOW_PATH=$(gitpath shallow); GRAFTS_PATH=$(gitpath info/grafts)
> IS_SHALLOW=$(git rev-parse --is-shallow-repository 2>/dev/null || echo unknown)
> SHALLOW_LIST=$( [ -f "$SHALLOW_PATH" ] && tr '\n' ' ' < "$SHALLOW_PATH" || printf '' )
> REPLACE_LIST=$(git replace -l 2>/dev/null | tr '\n' ' ')
> GRAFTS_PRESENT=$( [ -f "$GRAFTS_PATH" ] && echo yes || echo no )
> CAN_MIS=0; for x in $(git rev-list --all 2>/dev/null); do
>   tp=$(nset "$(parents_true "$x")"); ap=$(nset "$(parents_ambient "$x")"); [ "$tp" = "$ap" ] || CAN_MIS=$((CAN_MIS+1)); done
> printf 'U17-SNAP canary(스냅샷 «안»): HEAD=%s · replace -l=[%s] · %s=%s · is_shallow=%s · ㉠(cat-file 부모 == %%P) 불일치 %s건 / 커밋 %s개\n' \
>   "$(git rev-parse HEAD)" "$(printf '%s ' $REPLACE_LIST)" "$GRAFTS_PATH" "$GRAFTS_PRESENT" "$IS_SHALLOW" "$CAN_MIS" "$(git rev-list --all | grep -c .)"
> [ "$CAN_MIS" -eq 0 ] || emit PREVENTION_UNVERIFIABLE "[격리 스냅샷 canary] 스냅샷 안에서 ㉠ 불일치 ${CAN_MIS}건 — 기층 오염(--local 폴백·번들 오용 표면)"
103a143
> 
361c401,402
< print("OK" if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
---
> # [v2.20 #1(2)] 서버 스텝 대조에 쓸 run_id 를 «같은 응답»에서 회수한다 (별도 선언 아님 — 구조 파생)
> print(("OK|%s"%hit[0].get("id")) if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
364c405
<       [ "$WFOK" = OK ] || { IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue; }
---
>       case "$WFOK" in OK\|*) RUN_ID="${WFOK#OK|}" ;; *) IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue ;; esac
378,379c419,441
<     L1=$(printf '%s\n' "$WF" | grep -cF -- "$LIT1"); L2=$(printf '%s\n' "$WF" | grep -cF -- "$LIT2")
<     printf 'U17-B5 grep: %s → %s회 · %s → %s회\n' "$LIT1" "$L1" "$LIT2" "$L2"
---
>     # ── [v2.20 #1 (1)] 구조 파싱 — «문자열 존재»가 아니라 «실행 스텝 구조» (정규식·grep 아님)
>     WFF="$CAP/$(key "$CQ").wf.yml"; printf '%s\n' "$WF" > "$WFF"
>     WFOUT=$(WF_GATE_JOB="$CHECK" WF_HARNESS="$LIT1" WF_SHA="$LIT2" python3 "$WFSTRUCT" blob "$WFF" 2>&1); WFRC=$?
>     printf '%s\n' "$WFOUT" | sed 's/^/  | /'
>     WFRES=$(printf '%s\n' "$WFOUT" | sed -n 's/^RESULT=//p' | tail -1)
>     case "$WFRES" in
>       UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 구조 파싱 불가(YAML 파서 실패)"; continue ;;
>       BLOB_OK) : ;;
>       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)"; continue ;;
>     esac
>     # ── [v2.20 #1 (2)] 서버 잡 스텝 대조 — actions/runs/{run_id}/jobs (계약 리터럴 스텝 이름 × conclusion)
>     [ -n "${RUN_ID:-}" ] || { fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA run_id 미회수 — 서버 스텝 대조 불가"; continue; }
>     JQ="repos/$PIN_OR/actions/runs/$RUN_ID/jobs"; respond "$JQ"; show_capture B6 "$JQ"; JST=$(http_of "$JQ")
>     if [ "$JST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 조회 네트워크/인증 오류 — $JQ"; continue
>     elif ! ok2xx "$JST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d jobs http=$JST — 서버 스텝 기록 조회 실패(검사 생략 금지)"; continue; fi
>     SVOUT=$(WF_GATE_JOB="$CHECK" python3 "$WFSTRUCT" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?
>     printf '%s\n' "$SVOUT" | sed 's/^/  | /'
>     SVRES=$(printf '%s\n' "$SVOUT" | sed -n 's/^RESULT=//p' | tail -1)
>     case "$SVRES" in
>       UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 본문 파싱 실패"; continue ;;
>       SERVER_OK) : ;;
>       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)"; continue ;;
>     esac
381,382c443
<     { [ "$L1" -ge 1 ] && [ "$L2" -ge 1 ]; } || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 서버 워크플로 blob 에 리터럴 부재 (harness path=$L1 sha256=$L2)"; continue; }
<     printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
---
>     printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
```

## 3. (b)③ 구조 파싱 술어 — 픽스처 8종 (실행기 밖 단위 관측)

```text
########## B1. [v2.20 #1(1)] (b)③ 구조 파싱 술어 — 픽스처 8종 직접 실행 (YAML 파서 + 셸 토크나이저 · 실행기 밖 단위 관측) ##########
variant        기대(계약 T-84 ⑬ · (b)③)                    실측
ok             BLOB_OK (정상)                                     BLOB_OK
yamlcomment    UNVERIFIED_REVISION (YAML 주석 — 파서가 폐기) UNVERIFIED_REVISION
env            UNVERIFIED_REVISION (env: 값 — run 아님)        UNVERIFIED_REVISION
shcomment      UNVERIFIED_REVISION (full-line 셸 주석)           UNVERIFIED_REVISION
trailcomment   UNVERIFIED_REVISION (trailing 셸 주석 · ⑬b)    UNVERIFIED_REVISION
echoarg        UNVERIFIED_REVISION (echo 인자 위치 · ⑬a)     UNVERIFIED_REVISION
ortrue         BLOB_OK — «미검출»(⑬c 정직 경계)        BLOB_OK
echosha        UNVERIFIED_REVISION (echo <sha> = 비대조)         UNVERIFIED_REVISION

-- 대표 3종의 파싱 원문 (주석 제거 후 토큰·단순 명령 분해까지) --
== ok ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
```

### 3-1. 대표 3종의 파싱 원문 (주석 제거 후 토큰 → 단순 명령 분해 → 판정)

```text
== ok ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  WF-P7 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== trailcomment ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d\n'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['true']
  WF-P5 [verify] 단순 명령 분해 = [['true']]
  WF-P6 [verify] sha256 능동 대조 판정 = False (sha256 리터럴이 대조 명령의 피연산자로 실재하지 않음(주석·echo 인자·미사용 대입은 미충족))
  WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== ortrue ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d', 'true']
  WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'], ['true']]
  WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  WF-P7 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
```

## 4. 서버 잡 `steps[]` mock — 계약 리터럴 스텝 이름 2종 × conclusion

```text
########## B2. [v2.20 #1(2)] 서버 잡 steps[] mock — 계약 리터럴 스텝 이름 2종 × conclusion (실행기 밖 단위 관측) ##########
variant     기대                                         실측
ok          SERVER_OK                                      SERVER_OK
noverify    UNVERIFIED_REVISION (verify 스텝 부재 · ⑭) UNVERIFIED_REVISION
verifyfail  UNVERIFIED_REVISION (verify conclusion=failure · ⑭) UNVERIFIED_REVISION
norun       UNVERIFIED_REVISION (run harness 스텝 부재 · ⑭) UNVERIFIED_REVISION
jobfail     UNVERIFIED_REVISION (잡 conclusion=failure)   UNVERIFIED_REVISION
-- ok · verifyfail 원문 --
== ok ==
  WF-S1 서버 jobs[] 이름 = ['tos-gate']
  WF-S2 게이트 잡 conclusion = 'success'
  WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  WF-S5 서버 층 판정 = SERVER_OK
  RESULT=SERVER_OK
== verifyfail ==
  WF-S1 서버 jobs[] 이름 = ['tos-gate']
  WF-S2 게이트 잡 conclusion = 'success'
  WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'failure')]
  WF-S4 스텝 «tos-gate: verify harness sha256» conclusion='failure' ≠ success → UNVERIFIED_REVISION (T-84 ⑭)
  RESULT=UNVERIFIED_REVISION
```

## 5. 기대 / 실측 표 (전건)

| 케이스 | 계약 기대 | 실측 상태값 | rc | 일치 |
| --- | --- | --- | --- | --- |
| **⑬ 기준선** — 정상 워크플로 + 서버 스텝 success | `PREVENTION_ACTIVE` + rc=0 | `PREVENTION_ACTIVE` | 0 | ✅ |
| **⑬a** 하니스가 `echo` «인자 위치» | `PREVENTION_UNVERIFIED_REVISION` + 비-0 | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| ⑬a 판별력 대조 — v2.19 «두 리터럴 grep» 실행기 | 통과하면 심판 #1 지적의 실증 | **`PREVENTION_ACTIVE`** | **0** | ✅ 실패 실증 |
| **⑬b** sha256 대조가 **trailing 셸 주석** 안에만 | `PREVENTION_UNVERIFIED_REVISION` + 비-0 | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| ⑬b 판별력 대조 — v2.19 실행기 | 통과하면 실증 | **`PREVENTION_ACTIVE`** | **0** | ✅ 실패 실증 |
| **⑬c** `… | grep <sha> || true`(런타임 무효화) | **미검출**(정직 경계) = 통과 | `PREVENTION_ACTIVE` | 0 | ✅ 계약이 선언한 대로 «미검출» |
| ⑬ 추가 — YAML 주석에만 심은 blob | `UNVERIFIED_REVISION` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| **⑭** 서버 `steps[]` 에 verify 스텝 **부재** | `PREVENTION_UNVERIFIED_REVISION` + 비-0 | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| ⑭ 판별력 대조 — v2.19(서버 스텝 미대조) | 통과하면 v2.20 이 닫은 자리 | **`PREVENTION_ACTIVE`** | **0** | ✅ 실패 실증 |
| **⑭-b** verify 스텝 `conclusion=failure` | `UNVERIFIED_REVISION` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| **⑭-c** 게이트 잡 `conclusion=failure` | `UNVERIFIED_REVISION` | `PREVENTION_UNVERIFIED_REVISION` | 1 | ✅ |
| 회귀 **⑪-(a)** 연속성 정상(SIMULATED) | `PREVENTION_ACTIVE` | `PREVENTION_ACTIVE` | 0 | ✅ |
| 회귀 **⑪-(b)** off→merge→on(`updated_at > t_land`) | `PREVENTION_CONTINUITY_UNVERIFIABLE` | `PREVENTION_CONTINUITY_UNVERIFIABLE` | 1 | ✅ |
| ⑪-(b') 판별력 대조 — v2.18 실행기 | 연속성 미소비 → 통과 | **`PREVENTION_ACTIVE`** | **0** | ✅ 실패 실증 |
| 회귀 **⑫-1/2** live · `GH_HOST` override 하 상태 불변 | 불변 | `PREVENTION_INSUFFICIENT` → `PREVENTION_INSUFFICIENT` | 1 / 1 | ✅ 불변 |
| ⑫-4 대조군(`--hostname` 제거 + 재핀 제거) + override | 타 host 로 가서 접힘 | **`PREVENTION_UNVERIFIABLE`** | 1 | ✅ 민감도 실증 |
| ⑫-6 대조군 · override 없음 | 기준선과 동일 | `PREVENTION_INSUFFICIENT` | 1 | ✅ 델타=override 민감도 |
| 회귀 **⑤-a** 선언 target=비-default | `PREVENTION_TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 | ✅ |
| 회귀 **⑤-b** 선언 owner_repo=`octocat/Hello-World` | `PREVENTION_TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 | ✅ |
| 회귀 **⑩-a** 원격이 타 host(gitlab.com) | `PREVENTION_TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 | ✅ |
| 회귀 **⑩-b** 원격이 타 owner | `PREVENTION_TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 | ✅ |
| 회귀 **⑨-a** 착수 «후» 아티팩트 편집 | `PREVENTION_ARTIFACT_MUTATED`(7) | `PREVENTION_ARTIFACT_MUTATED` | 1 | ✅ |
| **본 저장소 현행** live 1회 | (실측 음성) | **`PREVENTION_ABSENT`**(2) — 아티팩트 HEAD 부재 | 1 | 실측 |

## 6. 격리 스냅샷 기층 — 본 저장소 실측 (canary · 비용)

```text
########## 본 저장소 현행 상태 — live 1회 (GET --hostname github.com) · 격리 스냅샷 기층 위에서 ##########
  HEAD=3d17ea66896062140679faa895463b13a65cd510 · .git 크기= 89M · size-pack: 26.95 MiB
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /Users/harris/Development/private/kis_unified_sts/.git/info/grafts=no · is_shallow=false · entry HEAD=3d17ea66896062140679faa895463b13a65cd510
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /Users/harris/Development/private/kis_unified_sts /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=3d17ea66896062140679faa895463b13a65cd510 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2228개
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
  [비용 실측] 격리 스냅샷 포함 전체 실행 시간 = 151초 (계약 «--no-local 은 판정 1회이므로 감수»의 실측치)
  [서버 쓰기 0] 이 드라이버의 gh 호출은 전부 `gh api -i --hostname github.com <GET path>` 다 — POST/PATCH/PUT/DELETE·설정 변경 0
```

- 본 저장소(`.git` 89M · `size-pack 26.95 MiB` · 커밋 2,228개) 스냅샷 canary: `replace -l` 공집합 · grafts 부재 · **㉠ 불일치 0건 / 2,228 커밋**.
- **비용 실측**: 격리 스냅샷 포함 live 판정 1회 = **151초**. 계약 :7120 «`--no-local` 은 진짜 pack 전송이나 판정 1회이므로 감수»의 실측치다(§9 M-2).

## 7. 실행 기록 (stdout 전문 · rc·`x-github-request-id` 포함)

### 7-1. `bash t84v220.sh` (1903행)

```text
t84v220_utc=2026-08-19T07:57:23Z
sha256(u17-verify-v220.sh)=67d636ce4ac4ff0b4a3da06d24b5551748c7408d3325aebd9f5ac56b264ed101
sha256(wfstruct-v220.py)=792aaa1e73d8ef854c7478577b0732191065b961802f5988687cc03299760dc1
sha256(u17-verify-v219e6.sh)=174b0c186266f3585b2a592eca8c0a6c0424e57899d9d3d8e40308fae3a920b5
sha256(u17-verify-v219-CTRL-nohost.sh)=c24bf96f0df70fd12724284e8667effd71181e2e71f27be06863586c4c4c0b7a
sha256(u17-verify-v218e.sh)=6b196756890f580058c38c4b8e1f44e39c95c1b4137a33377af2602ad414a15c
-- 판정 실행기 vs 직전 판 실행기 diff 행수 = 77 (v2.20 델타: 구조 파싱 2층 + 격리 스냅샷) --
git version = git version 2.38.0 · gh version = gh version 2.93.0 (2026-05-27)

########## A. [C6] 원시 host 프로브 — 심판 실측 프로브 재현 (실행기 밖 · GET-only) ##########
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts --jq .default_branch    # utc=2026-08-19T07:57:23Z
  | * Request to https://api.github.com/repos/kakao-harris-lee/kis_unified_sts
  | > GET /repos/kakao-harris-lee/kis_unified_sts HTTP/1.1
  | > Host: api.github.com
  | < HTTP/2.0 200 OK
  | * Request took 516.775584ms
  | main
  ⇒ --hostname 이 GH_HOST 를 이긴다: 요청 host = api.github.com

$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api repos/kakao-harris-lee/kis_unified_sts --jq .default_branch    # (--hostname 없음 = v2.18 거동)  utc=2026-08-19T07:57:23Z
  | * Request to https://example.invalid/api/v3/repos/kakao-harris-lee/kis_unified_sts
  | > GET /api/v3/repos/kakao-harris-lee/kis_unified_sts HTTP/1.1
  | > Host: example.invalid
  | * dial tcp: lookup example.invalid: no such host
  | * Request took 2.476625ms
  | error connecting to example.invalid
  ⇒ host 없는 명령은 GH_HOST 로 간다: https://example.invalid/api/v3/repos/... (심판 프로브 그대로)

########## T-84 ⑫-1 live — 기준선(override 없음) · 원격=핀 · 선언=핀 · D=∅ ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 361936b 2026-08-19T16:57:24+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 012d920 2026-08-19T16:57:24+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base/.git/info/grafts=no · is_shallow=false · entry HEAD=361936b3283cc899bd597f1fac3332757aecbfdb
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QQLgZGs31u/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=361936b3283cc899bd597f1fac3332757aecbfdb · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QQLgZGs31u/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.cKbH2IzHIO
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QQLgZGs31u/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QQLgZGs31u/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:57:26Z  http=200  x-github-request-id=F9E8:328E21:8ABE57:990593:6A8561E5
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:57:26Z  http=200  x-github-request-id=8D6C:335F3A:8991FC:97DC9C:6A8561E6  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:57:27Z  http=200  x-github-request-id=E3C3:346330:89F3D5:983BD7:6A8561E7
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:57:28Z  http=200  x-github-request-id=9CE4:335F3A:89941B:97DEF0:6A8561E8
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:57:28Z  http=200  x-github-request-id=61B2:33C891:8ED0F8:9D1CE4:6A8561E8
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:57:29Z  http=200  x-github-request-id=ACA5:19934D:895B50:97A4A7:6A8561E9
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[361936b3283cc899bd597f1fac3332757aecbfdb ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[361936b3283cc899bd597f1fac3332757aecbfdb ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QQLgZGs31u/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑫-2 live — GH_HOST=example.invalid + GH_ENTERPRISE_TOKEN=dummy 로 «실행기 전체»를 돌린다 → 상태값 불변이어야 한다 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 361936b 2026-08-19T16:57:24+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 012d920 2026-08-19T16:57:24+09:00 seed
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base/.git/info/grafts=no · is_shallow=false · entry HEAD=361936b3283cc899bd597f1fac3332757aecbfdb
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Y2ufyVJ3al/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=361936b3283cc899bd597f1fac3332757aecbfdb · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Y2ufyVJ3al/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aPES1bJ5Zi
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Y2ufyVJ3al/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Y2ufyVJ3al/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/host-base/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:57:36Z  http=200  x-github-request-id=4452:335F3A:899CAC:97E83E:6A8561EF
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:57:36Z  http=200  x-github-request-id=E5F1:177308:8AE408:992DDB:6A8561EF  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:57:37Z  http=200  x-github-request-id=C612:94A79:89ABB4:97F937:6A8561F0
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:57:37Z  http=200  x-github-request-id=FDF5:C76AD:8A86C5:98CFE1:6A8561F1
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:57:38Z  http=200  x-github-request-id=E58E:33C891:8EDD3C:9D2A3D:6A8561F2
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:57:39Z  http=200  x-github-request-id=CF9A:1DEFCF:8ADD49:992AD2:6A8561F2
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[361936b3283cc899bd597f1fac3332757aecbfdb ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[361936b3283cc899bd597f1fac3332757aecbfdb ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Y2ufyVJ3al/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑫-3 live — override 하에서 실행기가 실제로 어느 host 로 갔는가 (GH_DEBUG=api 요청 host 캡처) ##########
  주: 실행기는 gh 의 stderr 를 $U17_CAPTURE_DIR/<key>.err 로 보내므로 GH_DEBUG 출력은 그 파일에 남는다 — 실행 후 전수 grep 한다.
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.H9AZI5yT7c bash u17-verify-v220.sh <fixture>   # utc=2026-08-19T07:57:39Z
  (u17_rc=1)
$ grep -h '^\* Request to\|^> Host:' /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.H9AZI5yT7c/*.err | sort | uniq -c
  |    6 * Request to https://api.github.com/…
  |    6 > Host: api.github.com
  ⇒ 실행기의 «모든» 요청 host = api.github.com (override 무효)

########## T-84 ⑫-4 대조군 — «--hostname 제거 + GH_HOST 재핀 제거» 변형(v2.18 거동)을 같은 override 로 실행 → 타 host 로 가서 UNVERIFIABLE 로 접혀야 한다 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 361936b 2026-08-19T16:57:24+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 012d920 2026-08-19T16:57:24+09:00 seed
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_RESPONDER=gh bash u17-verify-v219-CTRL-nohost.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@UNRESOLVED
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=∅ (apps/github-actions http=ERR) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ro9B2aREtX
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=example.invalid · auth 전제 `gh auth status` → mode=live rc=1
  | example.invalid
  |   X Failed to log in to example.invalid using token (GH_ENTERPRISE_TOKEN)
  |   - Active account: true
  |   - The token in GH_ENTERPRISE_TOKEN is invalid.
  | 
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
  | 
  | github.daumkakao.com
  |   X Failed to log in to github.daumkakao.com using token (GH_ENTERPRISE_TOKEN)
  |   - Active account: true
  |   - The token in GH_ENTERPRISE_TOKEN is invalid.
  | 
  |   ✓ Logged in to github.daumkakao.com account harris-lee (keyring)
  |   - Active account: false
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-fire PREVENTION_UNVERIFIABLE: [C6] `gh auth status` 실패(rc=1) — 핀 host 인증 부재 (타 host 폴백 없음)
U17-A00 apps/github-actions  utc=2026-08-19T07:57:55Z  http=ERR  x-github-request-id=
  | error connecting to example.invalid
  | check your internet connection or https://githubstatus.com
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:57:55Z  http=ERR  x-github-request-id=  (.default_branch=∅)
U17-fire PREVENTION_UNVERIFIABLE: apps/github-actions 조회 실패(http=ERR) — Actions app id 파생 불가
U17-fire PREVENTION_UNVERIFIABLE: repos/kakao-harris-lee/kis_unified_sts 조회 실패(http=ERR) — default_branch 파생 불가
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
P_first=361936b3283cc899bd597f1fac3332757aecbfdb P_last=361936b3283cc899bd597f1fac3332757aecbfdb |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[C6] `gh auth status` 실패(rc=1) — 핀 host 인증 부재 (타 host 폴백 없음) [수집 3건 중 전순서 최소]
u17_rc=1

########## T-84 ⑫-5 대조군 host 캡처 — 대조군은 실제로 example.invalid 로 나간다 ##########
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.sjMfxMHPii bash u17-verify-v219-CTRL-nohost.sh <fixture>   # utc=2026-08-19T07:57:55Z
  (u17_rc=1)
$ grep -h '^\* Request to\|^> Host:' /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.sjMfxMHPii/*.err | sort | uniq -c
  |    2 * Request to https://example.invalid/…
  |    2 > Host: example.invalid
  ⇒ 대조군은 GH_HOST 가 지정한 타 host(example.invalid/api/v3)로 나가 조회가 전부 실패한다 — 그 host 가 응답을 주면 그 응답이 판정 입력이 된다(위조 표면)

########## T-84 ⑫-6 대조군 — override «없이» 같은 대조군 실행 (델타가 override 민감도임을 고정) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 361936b 2026-08-19T16:57:24+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 012d920 2026-08-19T16:57:24+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219-CTRL-nohost.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.f1Z6Clj4zL
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=∅(재핀 없음) · auth 전제 `gh auth status` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
  | 
  | github.daumkakao.com
  |   ✓ Logged in to github.daumkakao.com account harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T07:58:08Z  http=200  x-github-request-id=E27B:19934D:898C8B:97DA56:6A85620F
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:08Z  http=200  x-github-request-id=129B:33C891:8F0325:9D537C:6A85620F  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:09Z  http=200  x-github-request-id=22D5:1DEFCF:8B041A:995503:6A856210
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:09Z  http=200  x-github-request-id=23E1:1D7764:8AB95C:990900:6A856211
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:12Z  http=200  x-github-request-id=09DC:21B9D:8C276D:9A78E2:6A856212
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:58:14Z  http=200  x-github-request-id=AD05:328E21:8AFE5D:994B74:6A856216
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=361936b3283cc899bd597f1fac3332757aecbfdb P_last=361936b3283cc899bd597f1fac3332757aecbfdb |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## B1. [v2.20 #1(1)] (b)③ 구조 파싱 술어 — 픽스처 8종 직접 실행 (YAML 파서 + 셸 토크나이저 · 실행기 밖 단위 관측) ##########
variant        기대(계약 T-84 ⑬ · (b)③)                    실측
ok             BLOB_OK (정상)                                     BLOB_OK
yamlcomment    UNVERIFIED_REVISION (YAML 주석 — 파서가 폐기) UNVERIFIED_REVISION
env            UNVERIFIED_REVISION (env: 값 — run 아님)        UNVERIFIED_REVISION
shcomment      UNVERIFIED_REVISION (full-line 셸 주석)           UNVERIFIED_REVISION
trailcomment   UNVERIFIED_REVISION (trailing 셸 주석 · ⑬b)    UNVERIFIED_REVISION
echoarg        UNVERIFIED_REVISION (echo 인자 위치 · ⑬a)     UNVERIFIED_REVISION
ortrue         BLOB_OK — «미검출»(⑬c 정직 경계)        BLOB_OK
echosha        UNVERIFIED_REVISION (echo <sha> = 비대조)         UNVERIFIED_REVISION

-- 대표 3종의 파싱 원문 (주석 제거 후 토큰·단순 명령 분해까지) --
== ok ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  WF-P7 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== trailcomment ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d\n'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['true']
  WF-P5 [verify] 단순 명령 분해 = [['true']]
  WF-P6 [verify] sha256 능동 대조 판정 = False (sha256 리터럴이 대조 명령의 피연산자로 실재하지 않음(주석·echo 인자·미사용 대입은 미충족))
  WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== ortrue ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true
  WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  WF-P3 [run] bash -n rc=0 
  WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true'
  WF-P3 [verify] bash -n rc=0 
  WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d', 'true']
  WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'], ['true']]
  WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  WF-P7 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK

########## B2. [v2.20 #1(2)] 서버 잡 steps[] mock — 계약 리터럴 스텝 이름 2종 × conclusion (실행기 밖 단위 관측) ##########
variant     기대                                         실측
ok          SERVER_OK                                      SERVER_OK
noverify    UNVERIFIED_REVISION (verify 스텝 부재 · ⑭) UNVERIFIED_REVISION
verifyfail  UNVERIFIED_REVISION (verify conclusion=failure · ⑭) UNVERIFIED_REVISION
norun       UNVERIFIED_REVISION (run harness 스텝 부재 · ⑭) UNVERIFIED_REVISION
jobfail     UNVERIFIED_REVISION (잡 conclusion=failure)   UNVERIFIED_REVISION
-- ok · verifyfail 원문 --
== ok ==
  WF-S1 서버 jobs[] 이름 = ['tos-gate']
  WF-S2 게이트 잡 conclusion = 'success'
  WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  WF-S5 서버 층 판정 = SERVER_OK
  RESULT=SERVER_OK
== verifyfail ==
  WF-S1 서버 jobs[] 이름 = ['tos-gate']
  WF-S2 게이트 잡 conclusion = 'success'
  WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'failure')]
  WF-S4 스텝 «tos-gate: verify harness sha256» conclusion='failure' ≠ success → UNVERIFIED_REVISION (T-84 ⑭)
  RESULT=UNVERIFIED_REVISION

########## C. T-84 ⑬ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · blob 변형만 바뀐다 ##########
W(PR head)=c459e8cb93a038ccaef227cb56186abe76623990  d=bda9e5346bd793b1d97259f337292685c554b5f7

########## T-84 ⑬ 기준선 — 정상 워크플로(계약 리터럴 스텝 이름·하니스 실행·sha256 대조) + 서버 스텝 success ⇒ PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-ok bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Mcqdr3Y0WY/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Mcqdr3Y0WY/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-ok capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9qknQqSk3f
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-ok — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Mcqdr3Y0WY/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Mcqdr3Y0WY/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:17Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:17Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:17Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:17Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:17Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:17Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Mcqdr3Y0WY/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:18Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:18Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:18Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:19Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:19Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:19Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show c459e8cb93a038ccaef227cb56186abe76623990:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-ok
u17_rc=0

########## T-84 ⑬a — 하니스 경로가 «echo 인자» 위치 (실행 아님) ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hlcQNfqGb2/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hlcQNfqGb2/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.enomGAcy6p
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hlcQNfqGb2/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hlcQNfqGb2/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:21Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:21Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:21Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:21Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:21Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:21Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hlcQNfqGb2/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:22Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:22Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:22Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:22Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:22Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "e8cf6ab50cffd4ea4c75cc3e434e03131545606d", "size": 432, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIGVjaG8gIm5vdGU6IHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoIGlzIHJlZmVyZW5jZWQgYnV0IG5vdCBleGVjdXRlZCIKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=432):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: |
  |           echo "note: tools/tos_entry_harness.sh is referenced but not executed"
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'echo "note: tools/tos_entry_harness.sh is referenced but not executed"\n'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['echo', 'note: tools/tos_entry_harness.sh is referenced but not executed']
  | WF-P5 [run] 단순 명령 분해 = [['echo', 'note: tools/tos_entry_harness.sh is referenced but not executed']]
  | WF-P6 [run] 하니스 실행 판정 = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑬a 판별력 대조 — 같은 seam 을 «두 리터럴 grep» 직전 판 실행기(v2.19)로 실행 → 통과하면 그것이 심판 #1 이 지목한 실패다 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zYOlQUrPft
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:23Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:23Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:23Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:23Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:23Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:23Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:24Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:24Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:24Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:24Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:24Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "e8cf6ab50cffd4ea4c75cc3e434e03131545606d", "size": 432, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IHwKICAgICAgICAgIGVjaG8gIm5vdGU6IHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoIGlzIHJlZmVyZW5jZWQgYnV0IG5vdCBleGVjdXRlZCIKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=432):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: |
  |           echo "note: tools/tos_entry_harness.sh is referenced but not executed"
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show c459e8cb93a038ccaef227cb56186abe76623990:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13a
u17_rc=0

########## T-84 ⑬b — sha256 대조가 «trailing 셸 주석» 안에만 있고 실제 run 은 true ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.28bKckJLPW/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.28bKckJLPW/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KI10KYX64f
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.28bKckJLPW/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.28bKckJLPW/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:26Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:26Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:26Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:26Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:26Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:26Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.28bKckJLPW/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:27Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:27Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:27Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:27Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:28Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "c36a129b10ea5777d44c466871409e90ec3663d3", "size": 401, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHRydWUgICMgc2hhc3VtIC1hIDI1NiB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaCB8IGdyZXAgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=401):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d\n'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['true']
  | WF-P5 [verify] 단순 명령 분해 = [['true']]
  | WF-P6 [verify] sha256 능동 대조 판정 = False (sha256 리터럴이 대조 명령의 피연산자로 실재하지 않음(주석·echo 인자·미사용 대입은 미충족))
  | WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑬b 판별력 대조 — 같은 seam 을 직전 판 실행기(v2.19)로 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zD6tAmADgB
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:28Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:28Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:28Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:29Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:29Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:29Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:29Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:30Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:30Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:30Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:30Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "c36a129b10ea5777d44c466871409e90ec3663d3", "size": 401, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHRydWUgICMgc2hhc3VtIC1hIDI1NiB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaCB8IGdyZXAgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=401):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           true  # shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show c459e8cb93a038ccaef227cb56186abe76623990:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13b
u17_rc=0

########## T-84 ⑬c — «|| true» 런타임 무효화: 대조는 «능동 명령»이라 구조 파싱·서버 스텝 둘 다 통과 ⇒ PREVENTION_ACTIVE = «미검출»(계약이 선언한 정직 경계) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13c bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VLoqjyg9iR/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VLoqjyg9iR/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13c capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2y8sxUJeFX
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13c — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VLoqjyg9iR/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VLoqjyg9iR/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:31Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:31Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:32Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:32Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:32Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:32Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.VLoqjyg9iR/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "da12db993b3059756a4fa96c127f9a1fc484af72", "size": 389, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfHwgdHJ1ZQo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=389):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d || true'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d', 'true']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'], ['true']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:33Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show c459e8cb93a038ccaef227cb56186abe76623990:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-13c
u17_rc=0

########## T-84 ⑬ 추가 변형 — YAML 주석에만 심은 blob ⇒ UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-yaml bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7MIwkgsUK7/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7MIwkgsUK7/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-yaml capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ohqe59YHZI
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-yaml — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7MIwkgsUK7/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7MIwkgsUK7/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:35Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:35Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:35Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:35Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:35Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:35Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7MIwkgsUK7/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:36Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:36Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:36Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:36Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:37Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "e69e3fbc6e30cd9dbc97d9e696a4d3a1265a366f", "size": 344, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICAjIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgIHN0ZXBzOgogICAgICAtIHVzZXM6IGFjdGlvbnMvY2hlY2tvdXRAdjQKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogdHJ1ZQogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogdHJ1ZQo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=344):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     # tools/tos_entry_harness.sh 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: true
  |       - name: "tos-gate: verify harness sha256"
  |         run: true
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 실행문 부재(run 이 문자열 아님) → UNVERIFIED_REVISION
  | WF-P2 [verify] run: 실행문 부재(run 이 문자열 아님) → UNVERIFIED_REVISION
  | WF-P7 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## D. T-84 ⑭ — blob 구조는 «통과»하나 서버 잡 steps[] 에 계약 리터럴 스텝이 부재 ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixZqYKIc1I/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixZqYKIc1I/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.2UgvVSodPW
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixZqYKIc1I/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixZqYKIc1I/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:38Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:38Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:38Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:38Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:38Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:39Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixZqYKIc1I/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:39Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:40Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:40Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:40Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:40Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:40Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success')]
  | WF-S4 스텝 이름 «tos-gate: verify harness sha256» 서버 부재 → UNVERIFIED_REVISION (T-84 ⑭)
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑭ 판별력 대조 — 같은 seam 을 직전 판 실행기(v2.19 · 서버 스텝 미대조)로 → 통과하면 그것이 v2.20 이 닫은 자리다 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a bash u17-verify-v219e6.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.t4gpFHRvld
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:41Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:41Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:41Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:41Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:41Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:41Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:42Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:42Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:42Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:42Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:42Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show c459e8cb93a038ccaef227cb56186abe76623990:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14a
u17_rc=0

########## T-84 ⑭-b — verify 스텝 conclusion=failure ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14b bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FtUPbuq5DG/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FtUPbuq5DG/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ii8KOMztLM
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FtUPbuq5DG/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FtUPbuq5DG/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:44Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:44Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:44Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:44Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:44Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:44Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.FtUPbuq5DG/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:45Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:45Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:45Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:45Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:46Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:46Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"failure","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'failure')]
  | WF-S4 스텝 «tos-gate: verify harness sha256» conclusion='failure' ≠ success → UNVERIFIED_REVISION (T-84 ⑭)
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑭-c — 게이트 잡 자체가 conclusion=failure ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * bda9e53 2026-08-19T16:58:16+09:00 D0-A: introduce config/tos_completion.yaml
  * c459e8c 2026-08-19T16:58:16+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5598b41 2026-08-19T16:58:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 369bbdc 2026-08-19T16:58:15+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14c bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=bda9e5346bd793b1d97259f337292685c554b5f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pgrLLtfc2R/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=bda9e5346bd793b1d97259f337292685c554b5f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pgrLLtfc2R/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14c capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.fGshK6KqJG
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b3-14c — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pgrLLtfc2R/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pgrLLtfc2R/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:47Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:47Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:48Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:48Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:48Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:48Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5598b41dc13d9aa008b09a06aa2b9e22c4567b60 ] |D|=1 D=[bda9e5346bd793b1d97259f337292685c554b5f7 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pgrLLtfc2R/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/bda9e5346bd793b1d97259f337292685c554b5f7/pulls  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c459e8cb93a038ccaef227cb56186abe76623990"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c459e8cb93a038ccaef227cb56186abe76623990/check-runs  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c459e8cb93a038ccaef227cb56186abe76623990  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c459e8cb93a038ccaef227cb56186abe76623990 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:49Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"failure","head_sha":"c459e8cb93a038ccaef227cb56186abe76623990","steps":[{"name":"tos-gate: run harness","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'failure'
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=bda9e5346bd793b1d97259f337292685c554b5f7 head=c459e8cb93a038ccaef227cb56186abe76623990 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

########## ⑪ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · 이후 (a)~(f) 는 seam 만 바뀐다 ##########
W(PR head)=bed92889ec980d5aa7360718011e3e35d574f44f  d=6bc2391d424a482c5a45f8c102848c795939ac52

########## T-84 ⑪-(a) SIMULATED — 정상: 적용 룰셋 created_at·updated_at ≤ t_land(2026-08-10T00:00:00Z) → PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 6bc2391 2026-08-19T16:58:50+09:00 D0-A: introduce config/tos_completion.yaml
  * bed9288 2026-08-19T16:58:50+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * e807dd8 2026-08-19T16:58:50+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 22ea5f3 2026-08-19T16:58:50+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/a bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont/.git/info/grafts=no · is_shallow=false · entry HEAD=6bc2391d424a482c5a45f8c102848c795939ac52
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dfI8yRSDTY/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=6bc2391d424a482c5a45f8c102848c795939ac52 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dfI8yRSDTY/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ifZHwfbD7p
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dfI8yRSDTY/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dfI8yRSDTY/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:51Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:51Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:51Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:51Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:52Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:52Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[e807dd88e5b305d1cc79b10510ced453be6c09a0 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[e807dd88e5b305d1cc79b10510ced453be6c09a0 ] |D|=1 D=[6bc2391d424a482c5a45f8c102848c795939ac52 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dfI8yRSDTY/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/6bc2391d424a482c5a45f8c102848c795939ac52/pulls  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"bed92889ec980d5aa7360718011e3e35d574f44f"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/bed92889ec980d5aa7360718011e3e35d574f44f/check-runs  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=bed92889ec980d5aa7360718011e3e35d574f44f  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@bed92889ec980d5aa7360718011e3e35d574f44f (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:53Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show bed92889ec980d5aa7360718011e3e35d574f44f:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=6bc2391d424a482c5a45f8c102848c795939ac52 head=bed92889ec980d5aa7360718011e3e35d574f44f merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/a
u17_rc=0

########## T-84 ⑪-(b) SIMULATED — off→merge→on: updated_at(2026-08-11) > t_land(2026-08-10T00:00:00Z) → PREVENTION_CONTINUITY_UNVERIFIABLE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 6bc2391 2026-08-19T16:58:50+09:00 D0-A: introduce config/tos_completion.yaml
  * bed9288 2026-08-19T16:58:50+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * e807dd8 2026-08-19T16:58:50+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 22ea5f3 2026-08-19T16:58:50+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont/.git/info/grafts=no · is_shallow=false · entry HEAD=6bc2391d424a482c5a45f8c102848c795939ac52
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p2EBCavEp9/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=6bc2391d424a482c5a45f8c102848c795939ac52 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p2EBCavEp9/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.spmXXLz8bc
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p2EBCavEp9/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p2EBCavEp9/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/cont/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:58:55Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:55Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:55Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:55Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:55Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:55Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[e807dd88e5b305d1cc79b10510ced453be6c09a0 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[e807dd88e5b305d1cc79b10510ced453be6c09a0 ] |D|=1 D=[6bc2391d424a482c5a45f8c102848c795939ac52 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.p2EBCavEp9/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/6bc2391d424a482c5a45f8c102848c795939ac52/pulls  utc=2026-08-19T07:58:56Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"bed92889ec980d5aa7360718011e3e35d574f44f"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/bed92889ec980d5aa7360718011e3e35d574f44f/check-runs  utc=2026-08-19T07:58:56Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:56Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:56Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=bed92889ec980d5aa7360718011e3e35d574f44f  utc=2026-08-19T07:58:56Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@bed92889ec980d5aa7360718011e3e35d574f44f (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:58:57Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show bed92889ec980d5aa7360718011e3e35d574f44f:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=6bc2391d424a482c5a45f8c102848c795939ac52 head=bed92889ec980d5aa7360718011e3e35d574f44f merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님)
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=(α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑪-(b') 판별력 대조 — 같은 (b) seam 을 «직전 판» 실행기(u17-verify-v218e.sh)로 실행 → 연속성 미소비라 통과해야 한다(= v2.19 가 닫은 자리) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 6bc2391 2026-08-19T16:58:50+09:00 D0-A: introduce config/tos_completion.yaml
  * bed9288 2026-08-19T16:58:50+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * e807dd8 2026-08-19T16:58:50+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 22ea5f3 2026-08-19T16:58:50+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.254ZFY4psp
U17-A00 apps/github-actions  utc=2026-08-19T07:58:57Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:58:57Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:58:57Z  http=404
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:58:57Z  http=200
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:58:57Z  http=200
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:58:57Z  http=200
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α ruleset 42 created_at=2026-08-01T00:00:00Z updated_at=2026-08-11T09:00:00Z enforcement=active (관측 기록)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=e807dd88e5b305d1cc79b10510ced453be6c09a0 P_last=e807dd88e5b305d1cc79b10510ced453be6c09a0 |D|=1 D=6bc2391d424a482c5a45f8c102848c795939ac52 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/6bc2391d424a482c5a45f8c102848c795939ac52/pulls  utc=2026-08-19T07:58:58Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"bed92889ec980d5aa7360718011e3e35d574f44f"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/bed92889ec980d5aa7360718011e3e35d574f44f/check-runs  utc=2026-08-19T07:58:58Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:58:58Z  http=200
  | {"id":777001,"head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:58:58Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"bed92889ec980d5aa7360718011e3e35d574f44f","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=bed92889ec980d5aa7360718011e3e35d574f44f  utc=2026-08-19T07:58:58Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@bed92889ec980d5aa7360718011e3e35d574f44f (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show bed92889ec980d5aa7360718011e3e35d574f44f:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=6bc2391d424a482c5a45f8c102848c795939ac52 head=bed92889ec980d5aa7360718011e3e35d574f44f merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α ruleset 42: created_at=2026-08-01T00:00:00+00:00 ≤ merged_at(minD)=2026-08-10T00:00:00+00:00 · updated_at=2026-08-11T09:00:00+00:00 > merged_at (착수 후 변경됨) (관측 기록·차단 아님)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/b
u17_rc=0

########## 회귀 ⑤-a live — 선언 target=비-default 브랜치 → PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * ba5256a 2026-08-19T16:58:59+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 1e0f775 2026-08-19T16:58:59+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-wb/.git/info/grafts=no · is_shallow=false · entry HEAD=ba5256a9fec1060edb10868136eda0dd4d8eee9f
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-wb /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.U28HX5t5PU/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=ba5256a9fec1060edb10868136eda0dd4d8eee9f · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.U28HX5t5PU/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.vtXhLwLLdj
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.U28HX5t5PU/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.U28HX5t5PU/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-wb/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:59:06Z  http=200  x-github-request-id=7EBA:C76AD:8AF6EB:994A7C:6A856248
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:59:06Z  http=200  x-github-request-id=6ED5:177308:8B5975:99ADE6:6A856249  (.default_branch=main)
U17-T declared-vs-pin:  target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:59:08Z  http=200  x-github-request-id=6187:19934D:89DF1B:98341A:6A85624B
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:59:13Z  http=200  x-github-request-id=800E:389700:891E59:977558:6A85624D
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:59:13Z  http=200  x-github-request-id=3309:94A79:8A2ABE:98837A:6A856251
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:59:14Z  http=200  x-github-request-id=0C5A:335F3A:8A1CC2:987412:6A856252
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[ba5256a9fec1060edb10868136eda0dd4d8eee9f ] P_last(집합·|1|·blob=4721862ccfb97aa7352a29a7ee9f1c2d16d145ad)=[ba5256a9fec1060edb10868136eda0dd4d8eee9f ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.U28HX5t5PU/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) [수집 2건 중 전순서 최소]
u17_rc=1

########## 회귀 ⑤-b live — 선언 owner_repo=octocat/Hello-World → PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: octocat/Hello-World
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 71d61e4 2026-08-19T16:59:15+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 7478d91 2026-08-19T16:59:15+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-oct/.git/info/grafts=no · is_shallow=false · entry HEAD=71d61e478e1e630f059ae9e1e2988857e94dadd0
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-oct /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wepEStbifl/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=71d61e478e1e630f059ae9e1e2988857e94dadd0 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wepEStbifl/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aWjp4ALDyX
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wepEStbifl/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wepEStbifl/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/decl-oct/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:59:20Z  http=200  x-github-request-id=9B92:19934D:89ED70:9843D3:6A856257
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:59:20Z  http=200  x-github-request-id=5CEC:21B9D:8C8589:9ADF36:6A856258  (.default_branch=main)
U17-T declared-vs-pin:  owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) (declared owner_repo=octocat/Hello-World target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:59:21Z  http=200  x-github-request-id=BC67:94A79:8A34C2:988E58:6A856258
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:59:21Z  http=200  x-github-request-id=ED4E:C76AD:8B0B91:996141:6A856259
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:59:22Z  http=200  x-github-request-id=6CAB:11185E:8E844F:9CDC42:6A85625A
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:59:23Z  http=200  x-github-request-id=506D:C76AD:8B0D56:996331:6A85625A
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[71d61e478e1e630f059ae9e1e2988857e94dadd0 ] P_last(집합·|1|·blob=b4a54ba6b16b9e4a3524da195985e1ce804d6013)=[71d61e478e1e630f059ae9e1e2988857e94dadd0 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wepEStbifl/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## 회귀 ⑩-a live — 원격이 타 host 동일 경로(gitlab.com) → PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 5a01ee3 2026-08-19T16:59:24+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 4e253a7 2026-08-19T16:59:23+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-gitlab/.git/info/grafts=no · is_shallow=false · entry HEAD=5a01ee3fda1abcf3f36e9f7f060edada4283ca77
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-gitlab /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KPED7iVcqC/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=5a01ee3fda1abcf3f36e9f7f060edada4283ca77 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KPED7iVcqC/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=gitlab.com/kakao-harris-lee/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.wfWHOaaWUw
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KPED7iVcqC/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KPED7iVcqC/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-gitlab/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:59:26Z  http=200  x-github-request-id=226A:177308:8B72BC:99CA02:6A85625D
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:59:26Z  http=200  x-github-request-id=5053:389700:892EEB:97879D:6A85625E  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:59:27Z  http=200  x-github-request-id=6E72:33C891:8F6815:9DC1F3:6A85625F
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:59:27Z  http=200  x-github-request-id=0F67:389700:8930F0:9789D9:6A85625F
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:59:28Z  http=200  x-github-request-id=D31B:1DEFCF:8B68F5:99C373:6A856260
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:59:29Z  http=200  x-github-request-id=9AA7:C76AD:8B15A7:996C3E:6A856260
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[5a01ee3fda1abcf3f36e9f7f060edada4283ca77 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5a01ee3fda1abcf3f36e9f7f060edada4283ca77 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.KPED7iVcqC/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## 회귀 ⑩-b live — 원격이 타 owner(git@github.com:octocat/kis_unified_sts.git) → PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	git@github.com:octocat/kis_unified_sts.git (fetch)
  | origin	git@github.com:octocat/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 40194db 2026-08-19T16:59:30+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b6f2281 2026-08-19T16:59:30+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-oct/.git/info/grafts=no · is_shallow=false · entry HEAD=40194db0d46c19e566e24f1ade8cafbad6b7738d
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-oct /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OQupEKM8Xj/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=40194db0d46c19e566e24f1ade8cafbad6b7738d · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OQupEKM8Xj/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/octocat/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.9HnAB4AaIK
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OQupEKM8Xj/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OQupEKM8Xj/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/rem-oct/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:59:37Z  http=200  x-github-request-id=DEC5:177308:8B804B:99D865:6A856267
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:59:37Z  http=200  x-github-request-id=9842:201076:8B5C41:99B558:6A856268  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:59:38Z  http=200  x-github-request-id=8EFC:389700:893E13:97983D:6A856269
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:59:38Z  http=200  x-github-request-id=3FAF:328E21:8B6C60:99C353:6A85626A
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:59:39Z  http=200  x-github-request-id=D2AF:1DEFCF:8B772B:99D30E:6A85626B
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T07:59:40Z  http=200  x-github-request-id=3935:33C891:8F7868:9DD40E:6A85626C
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[40194db0d46c19e566e24f1ade8cafbad6b7738d ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[40194db0d46c19e566e24f1ade8cafbad6b7738d ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OQupEKM8Xj/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## 회귀 ⑨-a — P_first→W→d→P_edit (착수 «후» 아티팩트 편집) → PREVENTION_ARTIFACT_MUTATED (전순서 7 < 연속성 9) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED (edited AFTER d)
  * 2ee2f74 2026-08-19T16:59:41+09:00 P_edit: artifact edited after D0-A start (SIMULATED)
  * 995414a 2026-08-19T16:59:41+09:00 D0-A: introduce config/tos_completion.yaml
  * f2b1fd9 2026-08-19T16:59:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 14b4d1c 2026-08-19T16:59:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e7d68f3 2026-08-19T16:59:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/mut bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/mutated/.git/info/grafts=no · is_shallow=false · entry HEAD=2ee2f744eea5b294042935a584ff0639e9b8b7f7
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/mutated /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZzU3aulteq/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=2ee2f744eea5b294042935a584ff0639e9b8b7f7 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZzU3aulteq/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 5개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/mut capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.NbdNg2tJsM
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/seam220/mut — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZzU3aulteq/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZzU3aulteq/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence/fx84v220/mutated/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T07:59:43Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T07:59:43Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T07:59:43Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T07:59:43Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T07:59:43Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T07:59:43Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[14b4d1cabc621855232efb308f99df8d7cb1199c ] P_last(집합·|1|·blob=48c96a905c1eff6794582391c2dc1c558c983c12)=[2ee2f744eea5b294042935a584ff0639e9b8b7f7 ] |D|=1 D=[995414a0595ce8642f07b3ebdf1eabfc71f5b781 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ZzU3aulteq/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ ∃d∈D: x_last=2ee2f744eea5b294042935a584ff0639e9b8b7f7 ⋠ d — 착수 «후» 아티팩트 변경
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/995414a0595ce8642f07b3ebdf1eabfc71f5b781/pulls  utc=2026-08-19T07:59:44Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/f2b1fd986c06cbeac60f5512100b1657b13bea38/check-runs  utc=2026-08-19T07:59:44Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T07:59:44Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T07:59:44Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=f2b1fd986c06cbeac60f5512100b1657b13bea38  utc=2026-08-19T07:59:44Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "204d47144a9323df20bcc6ef908fec645f1647f0", "size": 381, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiBydW4gaGFybmVzcyIKICAgICAgICBydW46IGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQK\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@f2b1fd986c06cbeac60f5512100b1657b13bea38 (encoding=base64 size=381):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - uses: actions/checkout@v4
  |       - name: "tos-gate: run harness"
  |         run: bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = [None, 'tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'bash tools/tos_entry_harness.sh'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = 'shasum -a 256 tools/tos_entry_harness.sh | grep 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['shasum', '-a', '256', 'tools/tos_entry_harness.sh', 'grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']
  | WF-P5 [verify] 단순 명령 분해 = [['shasum', '-a', '256', 'tools/tos_entry_harness.sh'], ['grep', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (grep 인자에 sha256 리터럴 (대조 명령))
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T07:59:45Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"f2b1fd986c06cbeac60f5512100b1657b13bea38","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show f2b1fd986c06cbeac60f5512100b1657b13bea38:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=995414a0595ce8642f07b3ebdf1eabfc71f5b781 head=f2b1fd986c06cbeac60f5512100b1657b13bea38 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ ∃d∈D: x_last=2ee2f744eea5b294042935a584ff0639e9b8b7f7 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## 본 저장소 현행 상태 — live 1회 (GET --hostname github.com) · 격리 스냅샷 기층 위에서 ##########
  HEAD=3d17ea66896062140679faa895463b13a65cd510 · .git 크기= 89M · size-pack: 26.95 MiB
$ bash u17-verify-v220.sh /Users/harris/Development/private/kis_unified_sts
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /Users/harris/Development/private/kis_unified_sts/.git/info/grafts=no · is_shallow=false · entry HEAD=3d17ea66896062140679faa895463b13a65cd510
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /Users/harris/Development/private/kis_unified_sts /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=3d17ea66896062140679faa895463b13a65cd510 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2228개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.md2CYutfBm
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/Users/harris/Development/private/kis_unified_sts/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T08:02:10Z  http=200  x-github-request-id=1297:1DEFCF:8C40E5:9AAE71:6A856301
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T08:02:10Z  http=200  x-github-request-id=6F8F:346330:8B6C2D:99D594:6A856302  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T08:02:11Z  http=200  x-github-request-id=8445:11185E:8F65E9:9DD1C4:6A856303
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T08:02:12Z  http=200  x-github-request-id=DDFE:21B9D:8D6B48:9BD93B:6A856303
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T08:02:12Z  http=200  x-github-request-id=7D80:389700:8A0BDD:98781A:6A856304
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T08:02:16Z  http=200  x-github-request-id=5E66:328E21:8C3C75:9AA633:6A856308
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|0|)=[ ] P_last(집합·|0|·blob=∅)=[ ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 0건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.b8KsXf7KVc/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
  [비용 실측] 격리 스냅샷 포함 전체 실행 시간 = 151초 (계약 «--no-local 은 판정 1회이므로 감수»의 실측치)
  [서버 쓰기 0] 이 드라이버의 gh 호출은 전부 `gh api -i --hostname github.com <GET path>` 다 — POST/PATCH/PUT/DELETE·설정 변경 0
```

## 8. 실행기·술어·드라이버 원문

### 8-1. 판정 실행기 `u17-verify-v220.sh` (sha256 `67d636ce4ac4ff0b4a3da06d24b5551748c7408d3325aebd9f5ac56b264ed101` · 481행)

```bash
#!/usr/bin/env bash
# u17-verify (v2.20 동결 3d17ea66) — U-17 «예방 통제 활성 증거» 실행기 (계약 3d17ea66 §12.3.4 U-17)
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
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfstruct-v220.py}"   # [v2.20 #1] 구조 파싱 술어 (YAML 파서·셸 토크나이저)
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
DECL_OR=$(yv owner_repo); DECL_TB=$(yv target_branch); CHECK=$(yv tos_gate_check); [ -n "$CHECK" ] || CHECK=tos-gate
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
  printf 'U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)\n'
elif [ -n "$TARGET" ]; then
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
# [v2.20 #1(2)] 서버 스텝 대조에 쓸 run_id 를 «같은 응답»에서 회수한다 (별도 선언 아님 — 구조 파생)
print(("OK|%s"%hit[0].get("id")) if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
PY
)
      case "$WFOK" in OK\|*) RUN_ID="${WFOK#OK|}" ;; *) IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue ;; esac
      IDENT_OK=1; break
    done
    [ "$IDENT_OK" = 1 ] || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 워크플로 정체성 불충족:${IDENT_WHY:- 후보 없음}"; continue; }
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
    # ── [v2.20 #1 (1)] 구조 파싱 — «문자열 존재»가 아니라 «실행 스텝 구조» (정규식·grep 아님)
    WFF="$CAP/$(key "$CQ").wf.yml"; printf '%s\n' "$WF" > "$WFF"
    WFOUT=$(WF_GATE_JOB="$CHECK" WF_HARNESS="$LIT1" WF_SHA="$LIT2" python3 "$WFSTRUCT" blob "$WFF" 2>&1); WFRC=$?
    printf '%s\n' "$WFOUT" | sed 's/^/  | /'
    WFRES=$(printf '%s\n' "$WFOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$WFRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 구조 파싱 불가(YAML 파서 실패)"; continue ;;
      BLOB_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)"; continue ;;
    esac
    # ── [v2.20 #1 (2)] 서버 잡 스텝 대조 — actions/runs/{run_id}/jobs (계약 리터럴 스텝 이름 × conclusion)
    [ -n "${RUN_ID:-}" ] || { fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA run_id 미회수 — 서버 스텝 대조 불가"; continue; }
    JQ="repos/$PIN_OR/actions/runs/$RUN_ID/jobs"; respond "$JQ"; show_capture B6 "$JQ"; JST=$(http_of "$JQ")
    if [ "$JST" = ERR ]; then fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 조회 네트워크/인증 오류 — $JQ"; continue
    elif ! ok2xx "$JST"; then fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d jobs http=$JST — 서버 스텝 기록 조회 실패(검사 생략 금지)"; continue; fi
    SVOUT=$(WF_GATE_JOB="$CHECK" python3 "$WFSTRUCT" server "$CAP/$(key "$JQ").body" 2>&1); SVRC=$?
    printf '%s\n' "$SVOUT" | sed 's/^/  | /'
    SVRES=$(printf '%s\n' "$SVOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$SVRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d jobs 본문 파싱 실패"; continue ;;
      SERVER_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)"; continue ;;
    esac
    if git cat-file -e "$HSHA^{commit}" 2>/dev/null; then LB=$(git rev-parse -q --verify "$HSHA:$WF_PATH" 2>/dev/null || echo ABSENT); printf 'U17-B5x 보조(선택·판정 미소비): 로컬 git show %s:%s → %s\n' "$HSHA" "$WF_PATH" "$LB"; else printf 'U17-B5x 보조(선택·판정 미소비): 로컬에 %s 커밋 없음 — 서버 조회만으로 판정\n' "$HSHA"; fi
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
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

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```

### 8-2. 구조 파싱 술어 `wfstruct-v220.py` (sha256 `792aaa1e73d8ef854c7478577b0732191065b961802f5988687cc03299760dc1` · 251행)

```python
#!/usr/bin/env python3
"""U-17 (b)③ «구조 파싱» 술어 — v2.20 계약 3d17ea66 :5452-5486 의 문자 구현.

계약 문언(요약 인용):
  (1) blob 구조 파싱(정규식 아님) — YAML 파서로 파싱해 «주석»을 배제하고 `jobs.<게이트 잡>.steps[]` 만 본다.
      소비 대상은 각 스텝의 `run:` 실행문 «뿐»(`name:`·`env:`·기타 문자열 필드 제외)이며
      `run:` 셸 스크립트는 «셸 토크나이즈»(단어 분해·`#` 주석[full-line·trailing 둘 다] 제거·`bash -n` 파스)해 본다:
        (i)  `name: "tos-gate: run harness"` 스텝의 run 토큰열에서 하니스 경로가 «명령 위치»에 실재
             (`echo "…경로…"` 같은 «인자 위치»는 미충족)
        (ii) `name: "tos-gate: verify harness sha256"` 스텝의 run 실행문이 sha256 리터럴을 «대조»
             (`| grep <값>`·`[ "$x" = <값> ]`·`… | sha256sum -c` — 주석·미사용 대입이면 미충족)
      불충족 → PREVENTION_UNVERIFIED_REVISION (T-84 ⑬a·⑬b)
      정직 경계: `|| true` 류 «런타임 무효화»는 구문상 능동 대조라 통과한다 (T-84 ⑬c — 미검출)
  (2) 서버 잡 스텝 대조 — actions/runs/{run_id}/jobs 의 그 잡 conclusion==success ∧
      두 «스텝 이름»이 각각 conclusion==success 로 실재 (부재·실패 → UNVERIFIED_REVISION · T-84 ⑭)

YAML 파서: `yq -o=json`(mikefarah — 진짜 YAML 파서·주석 폐기).  정규식·grep 으로 blob 을 읽지 않는다.
출력: `WF-*` 라인(관측) + 마지막 줄 `RESULT=BLOB_OK|UNVERIFIED_REVISION|UNVERIFIABLE` · rc 0/1/2.
"""
import json, os, subprocess, sys

GATE_JOB = os.environ.get("WF_GATE_JOB", "tos-gate")
HARNESS  = os.environ.get("WF_HARNESS", "tools/tos_entry_harness.sh")
SHA      = os.environ.get("WF_SHA", "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d")
STEP_RUN = os.environ.get("WF_STEP_RUN", "tos-gate: run harness")
STEP_VER = os.environ.get("WF_STEP_VER", "tos-gate: verify harness sha256")
INTERP   = {"bash", "sh", "zsh", "dash", "ksh"}
CMPCMD   = {"grep", "egrep", "fgrep", "[", "test", "diff", "cmp", "sha256sum", "shasum", "awk"}
OPS      = {"|", "||", "&&", ";", "&", "\n", "(", ")", "{", "}", "|&", ";;"}


# ── 셸 토크나이저 (따옴표 인지 · `#` 주석 full-line/trailing 둘 다 제거) ────────────
def tokenize(script):
    toks, i, n = [], 0, len(script)
    word, quoted, started = "", False, False
    def flush():
        nonlocal word, quoted, started
        if started:
            toks.append({"w": word, "q": quoted, "op": False})
        word, quoted, started = "", False, False
    while i < n:
        ch = script[i]
        if ch == "#" and not started:                      # 주석 시작(단어 경계) — full-line·trailing 공통
            while i < n and script[i] != "\n":
                i += 1
            continue
        if ch in "'\"":
            q, i, buf = ch, i + 1, ""
            while i < n and script[i] != q:
                if q == '"' and script[i] == "\\" and i + 1 < n:
                    buf += script[i + 1]; i += 2; continue
                buf += script[i]; i += 1
            i += 1
            word += buf; quoted = True; started = True
            continue
        if ch == "\\" and i + 1 < n:
            word += script[i + 1]; started = True; i += 2; continue
        if ch in " \t":
            flush(); i += 1; continue
        if ch == "\n":
            flush(); toks.append({"w": "\n", "q": False, "op": True}); i += 1; continue
        two = script[i:i + 2]
        if two in ("||", "&&", "|&", ";;"):
            flush(); toks.append({"w": two, "q": False, "op": True}); i += 2; continue
        if ch in "|;&()":
            flush(); toks.append({"w": ch, "q": False, "op": True}); i += 1; continue
        word += ch; started = True; i += 1
    flush()
    return toks


def commands(toks):
    """연산자(`|` `||` `&&` `;` 개행 …)로 분해한 «단순 명령» 목록."""
    out, cur = [], []
    for t in toks:
        if t["op"]:
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def head_of(cmd):
    """선행 `VAR=val` 대입을 건너뛴 «명령 위치» 토큰과 인자 목록."""
    i = 0
    while i < len(cmd) and (not cmd[i]["q"]) and "=" in cmd[i]["w"] and not cmd[i]["w"].startswith("="):
        k = cmd[i]["w"].split("=", 1)[0]
        if k and all(c.isalnum() or c == "_" for c in k):
            i += 1
        else:
            break
    if i >= len(cmd):
        return None, []
    return cmd[i], cmd[i + 1:]


def base(p):
    return p.rsplit("/", 1)[-1]


def harness_called(cmds, strict_first_word=False):
    """하니스가 «실행»되는가.
    strict_first_word=True 는 계약 문언 «첫 단어»의 «문자» 구현(대조 관측용) —
    `bash tools/…` 를 미충족으로 본다.  기본(False)은 인터프리터 인자 위치까지 «실행»으로 인정한다."""
    for cmd in cmds:
        h, args = head_of(cmd)
        if h is None:
            continue
        w = h["w"]
        if w == HARNESS or w == "./" + HARNESS or base(w) == base(HARNESS) and w.endswith(HARNESS):
            return True, "명령 위치 = %s" % w
        if strict_first_word:
            continue
        j = 0
        if base(w) == "env":
            while j < len(args) and "=" in args[j]["w"]:
                j += 1
            if j < len(args):
                w = args[j]["w"]; args = args[j + 1:]
        if base(w) in INTERP:
            for a in args:
                if a["w"].startswith("-"):
                    continue
                if a["w"] == HARNESS or a["w"].endswith("/" + HARNESS) or a["w"] == "./" + HARNESS:
                    return True, "인터프리터 실행 = %s %s" % (w, a["w"])
                break
    return False, "실행 위치(명령·인터프리터 스크립트 인자)에 %s 부재" % HARNESS


def sha_compared(cmds):
    """sha256 리터럴이 «대조 피연산자»로 능동 소비되는가 (echo/printf 인자·미사용 대입은 미충족)."""
    for cmd in cmds:
        h, args = head_of(cmd)
        if h is None:
            continue
        b = base(h["w"])
        has = any(SHA in t["w"] for t in [h] + args)
        if b in ("echo", "printf", ":", "true"):
            continue
        if has and b in CMPCMD:
            return True, "%s 인자에 sha256 리터럴 (대조 명령)" % b
        if has and b in ("if", "while"):
            return True, "조건문 피연산자"
    for cmd in cmds:                                  # `sha256sum -c` / `shasum -c` 형태 (리터럴은 파일·heredoc)
        h, args = head_of(cmd)
        if h is None:
            continue
        if base(h["w"]) in ("sha256sum", "shasum") and any(a["w"] == "-c" or a["w"] == "--check" for a in args):
            return True, "%s -c 체크섬 대조" % base(h["w"])
    return False, "sha256 리터럴이 대조 명령의 피연산자로 실재하지 않음(주석·echo 인자·미사용 대입은 미충족)"


def parse_yaml(path):
    r = subprocess.run(["yq", "-o=json", ".", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, "yq 파싱 실패: " + r.stderr.strip()[:200]
    try:
        return json.loads(r.stdout), ""
    except Exception as e:
        return None, "JSON 변환 실패: %r" % (e,)


def blob_layer(path):
    doc, why = parse_yaml(path)
    print("WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.%s.steps[] · 소비 필드 = run: «뿐»" % GATE_JOB)
    if doc is None:
        print("WF-P1 " + why)
        return "UNVERIFIABLE"
    jobs = (doc or {}).get("jobs") or {}
    if GATE_JOB not in jobs:
        print("WF-P1 게이트 잡 «%s» 부재 (jobs=%s)" % (GATE_JOB, list(jobs)))
        return "UNVERIFIED_REVISION"
    steps = (jobs[GATE_JOB] or {}).get("steps") or []
    names = [s.get("name") for s in steps]
    print("WF-P1 steps[] 이름 = %s" % names)
    verdict = "BLOB_OK"
    for want, kind in ((STEP_RUN, "run"), (STEP_VER, "verify")):
        hit = [s for s in steps if s.get("name") == want]
        if not hit:
            print("WF-P2 [%s] 스텝 이름 «%s» 부재 → UNVERIFIED_REVISION" % (kind, want))
            verdict = "UNVERIFIED_REVISION"
            continue
        run = hit[0].get("run")
        if not isinstance(run, str):
            print("WF-P2 [%s] run: 실행문 부재(run 이 문자열 아님) → UNVERIFIED_REVISION" % kind)
            verdict = "UNVERIFIED_REVISION"
            continue
        print("WF-P2 [%s] run: 원문 = %r" % (kind, run))
        pn = subprocess.run(["bash", "-n"], input=run, capture_output=True, text=True)
        print("WF-P3 [%s] bash -n rc=%d %s" % (kind, pn.returncode, pn.stderr.strip()[:120]))
        if pn.returncode != 0:
            verdict = "UNVERIFIED_REVISION"
            continue
        toks = tokenize(run)
        cmds = commands(toks)
        print("WF-P4 [%s] 주석 제거 후 토큰 = %s" % (kind, [t["w"] for t in toks if not t["op"]]))
        print("WF-P5 [%s] 단순 명령 분해 = %s" % (kind, [[t["w"] for t in c] for c in cmds]))
        if kind == "run":
            ok, why2 = harness_called(cmds)
            oks, why3 = harness_called(cmds, strict_first_word=True)
            print("WF-P6 [run] 하니스 실행 판정 = %s (%s)" % (ok, why2))
            print("WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = %s (%s)" % (oks, why3))
        else:
            ok, why2 = sha_compared(cmds)
            print("WF-P6 [verify] sha256 능동 대조 판정 = %s (%s)" % (ok, why2))
        if not ok:
            verdict = "UNVERIFIED_REVISION"
    print("WF-P7 blob 층 판정 = %s" % verdict)
    return verdict


def server_layer(path):
    """actions/runs/{run_id}/jobs 응답(JSON 파일)에서 게이트 잡·두 스텝 이름·conclusion 대조."""
    try:
        j = json.load(open(path))
    except Exception as e:
        print("WF-S0 jobs 응답 파싱 실패 %r → UNVERIFIABLE" % (e,))
        return "UNVERIFIABLE"
    jobs = j.get("jobs") or []
    hit = [x for x in jobs if x.get("name") == GATE_JOB]
    print("WF-S1 서버 jobs[] 이름 = %s" % [x.get("name") for x in jobs])
    if not hit:
        print("WF-S2 게이트 잡 «%s» 서버 기록 부재 → UNVERIFIED_REVISION" % GATE_JOB)
        return "UNVERIFIED_REVISION"
    job = hit[0]
    print("WF-S2 게이트 잡 conclusion = %r" % job.get("conclusion"))
    if job.get("conclusion") != "success":
        return "UNVERIFIED_REVISION"
    steps = job.get("steps") or []
    print("WF-S3 서버 steps[] = %s" % [(s.get("name"), s.get("conclusion")) for s in steps])
    for want in (STEP_RUN, STEP_VER):
        m = [s for s in steps if s.get("name") == want]
        if not m:
            print("WF-S4 스텝 이름 «%s» 서버 부재 → UNVERIFIED_REVISION (T-84 ⑭)" % want)
            return "UNVERIFIED_REVISION"
        if m[0].get("conclusion") != "success":
            print("WF-S4 스텝 «%s» conclusion=%r ≠ success → UNVERIFIED_REVISION (T-84 ⑭)" % (want, m[0].get("conclusion")))
            return "UNVERIFIED_REVISION"
    print("WF-S5 서버 층 판정 = SERVER_OK")
    return "SERVER_OK"


if __name__ == "__main__":
    mode = sys.argv[1]
    res = blob_layer(sys.argv[2]) if mode == "blob" else server_layer(sys.argv[2])
    print("RESULT=" + res)
    sys.exit(0 if res in ("BLOB_OK", "SERVER_OK") else (2 if res == "UNVERIFIABLE" else 1))
```

### 8-3. 드라이버 `t84v220.sh` (sha256 `68a4102da4b31c2779565e3cfa3b118d8f0b2acf140a1e7b25f0d831fe0126e5` · 268행)

```bash
#!/usr/bin/env bash
# t84v220.sh — v2.20(계약 3d17ea66) T-84 드라이버: ⑬(비활성 리터럴 a/b/c) · ⑭(서버 잡 스텝 부재/실패)
#   + (b)③ 구조 파싱 술어 픽스처 8종 + 서버 steps[] mock 4종 + 회귀(⑤⑩ live TARGET_MISMATCH · ⑨ · ⑪(a)(b) · ⑫).
#   t84v219.sh 에서 파생 — 실행기 교체(v220) · 워크플로 픽스처를 «계약 리터럴 스텝 이름»으로 재작성 · jobs seam 추가.
# GET-only(gh api 조회만) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
SP19=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v220.sh"                      # 판정 실행기 (구조 파싱 + 서버 스텝 + 격리 스냅샷)
WFS="$SP/wfstruct-v220.py"                       # (b)③ 구조 파싱 술어
EX219="$SP19/u17-verify-v219e6.sh"               # 직전 판 실행기 — «두 리터럴 grep» (⑬⑭ 판별력 대조)
CTRL="$SP19/u17-verify-v219-CTRL-nohost.sh"; EX218="$SP19/u17-verify-v218e.sh"
FX="$SP/fx84v220"; SEAM="$SP/seam220"
PC=tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md; WF=.github/workflows/tos-gate.yml
OR=kakao-harris-lee/kis_unified_sts; PINURL=https://github.com/kakao-harris-lee/kis_unified_sts.git
WB=mission-critical-trading-operating-system; REPO=/Users/harris/Development/private/kis_unified_sts
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
TLAND=2026-08-10T00:00:00Z
export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=f@x GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=f@x
sec(){ printf '\n########## %s ##########\n' "$*"; }
mk(){ rm -rf "$1"; git init -q -b main "$1"; git -C "$1" remote add origin "${2:-$PINURL}"; printf 'seed\n' > "$1/seed.md"; git -C "$1" add -A; git -C "$1" commit -q -m seed; }
art(){ mkdir -p "$1/$(dirname $PC)"; { [ -n "${2:-}" ] && printf 'owner_repo: %s\n' "$2"; [ -n "${3:-}" ] && printf 'target_branch: %s\n' "$3"; printf 'tos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture\n'; } > "$1/$PC"
  git -C "$1" add -A; git -C "$1" commit -q -m "P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys $([ -n "${2:-}" ] && echo present || echo absent))"; git -C "$1" rev-parse HEAD; }
# [v2.20] 워크플로 본문 — 계약 리터럴 «스텝 이름» 2종.  variant: ok | echoarg(⑬a) | trailcomment(⑬b) | ortrue(⑬c) | yamlcomment | env | shcomment | echosha
wfcontent(){ local v="${1:-ok}"
  printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n'
  case "$v" in
    env) printf '    env:\n      HARNESS: tools/tos_entry_harness.sh\n      EXPECT: "%s"\n' "$LIT2" ;;
    yamlcomment) printf '    # tools/tos_entry_harness.sh %s\n' "$LIT2" ;;
  esac
  printf '    steps:\n      - uses: actions/checkout@v4\n      - name: "tos-gate: run harness"\n'
  case "$v" in
    echoarg)     printf '        run: |\n          echo "note: tools/tos_entry_harness.sh is referenced but not executed"\n' ;;
    yamlcomment|env) printf '        run: true\n' ;;
    shcomment)   printf '        run: |\n          # tools/tos_entry_harness.sh\n          true\n' ;;
    *)           printf '        run: bash tools/tos_entry_harness.sh\n' ;;
  esac
  printf '      - name: "tos-gate: verify harness sha256"\n'
  case "$v" in
    trailcomment) printf '        run: |\n          true  # shasum -a 256 tools/tos_entry_harness.sh | grep %s\n' "$LIT2" ;;
    ortrue)       printf '        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s || true\n' "$LIT2" ;;
    yamlcomment|env) printf '        run: true\n' ;;
    shcomment)    printf '        run: |\n          # shasum -a 256 tools/tos_entry_harness.sh | grep %s\n          true\n' "$LIT2" ;;
    echosha)      printf '        run: |\n          shasum -a 256 tools/tos_entry_harness.sh\n          echo %s\n' "$LIT2" ;;
    *)            printf '        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n' "$LIT2" ;;
  esac; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent "${2:-ok}" > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED)"; git -C "$1" rev-parse HEAD; }
d0a(){ mkdir -p "$1/config"; printf '# D0-A first artifact\n' > "$1/config/tos_completion.yaml"; git -C "$1" add -A; git -C "$1" commit -q -m "D0-A: introduce config/tos_completion.yaml"; git -C "$1" rev-parse HEAD; }
run(){ # run <repo> [responder] [executor] [env-prefix-label] — env 는 호출자가 앞에 붙인다
  echo "-- remotes --"; git -C "$1" remote -v | sed 's/^/  | /'
  echo "-- artifact @HEAD --"; git -C "$1" show "HEAD:$PC" 2>/dev/null | sed 's/^/  | /'
  git -C "$1" log --oneline --graph --format='%h %ad %s' --date=iso-strict | sed 's/^/  /'
  echo "\$ ${4:-}U17_RESPONDER=${2:-gh} bash $(basename "${3:-$EX}") <fixture>"
  env ${4:-} U17_RESPONDER="${2:-gh}" U17_CAPTURE_DIR="$(mktemp -d)" bash "${3:-$EX}" "$1"; echo "u17_rc=$?"; }
k(){ printf '%s' "$1" | tr '/?=&' '____'; }
inject(){ mkdir -p "$1"; printf '%s\n' "$3" > "$1/$(k "$2").status"; if [ -f "$4" ]; then cp "$4" "$1/$(k "$2").body"; else printf '%s\n' "$4" > "$1/$(k "$2").body"; fi; }
ACT='{"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}'
RULES_APPLIED(){ printf '[{"type":"required_status_checks","ruleset_id":%s,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":%s},{"type":"non_fast_forward","ruleset_id":%s},{"type":"deletion","ruleset_id":%s}]' "$1" "$1" "$1" "$1"; }
RSET_ONE(){ printf '{"id":%s,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"%s","updated_at":"%s","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}' "$1" "$2" "$3"; }
RSET_LIST(){ printf '[{"id":%s,"name":"protect_main","target":"branch","enforcement":"active","created_at":"%s","updated_at":"%s"}]' "$1" "$2" "$3"; }
base_common(){ inject "$1" "apps/github-actions" 200 '{"id":15368,"slug":"github-actions","name":"GitHub Actions"}'; inject "$1" "repos/$OR" 200 '{"full_name":"kakao-harris-lee/kis_unified_sts","default_branch":"main"}'; }
seam_ruleset(){ # seam_ruleset <dir> <ruleset id> <created_at> <updated_at>
  rm -rf "$1"; mkdir -p "$1"; base_common "$1"
  inject "$1" "repos/$OR/branches/main/protection" 404 '{"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}'
  inject "$1" "repos/$OR/rules/branches/main" 200 "$(RULES_APPLIED "$2")"
  inject "$1" "repos/$OR/rulesets" 200 "$(RSET_LIST "$2" "$3" "$4")"
  inject "$1" "repos/$OR/rulesets/$2" 200 "$(RSET_ONE "$2" "$3" "$4")"; }
seam_classic(){ # seam_classic <dir> — classic branch protection 만 (적용 룰셋 0)
  rm -rf "$1"; mkdir -p "$1"; base_common "$1"
  inject "$1" "repos/$OR/branches/main/protection" 200 "$ACT"
  inject "$1" "repos/$OR/rules/branches/main" 200 '[]'
  inject "$1" "repos/$OR/rulesets" 200 '[]'; }
contents_json(){ python3 - "$1" "$2" "$3" <<'PY'
import json,sys,base64
t=open(sys.argv[1],'rb').read()
print(json.dumps({"name":sys.argv[3].split("/")[-1],"path":sys.argv[3],"sha":sys.argv[2],"size":len(t),"type":"file","encoding":"base64","content":base64.b64encode(t).decode()+"\n"}))
PY
}
rev_seam(){ # rev_seam <dir> <d> <head> <suite> <merged_at|NOPR> [wf-variant] [jobs-variant]
  local dir="$1" d="$2" h="$3" s="$4" m="$5" wfv="${6:-ok}" jv="${7:-ok}"
  if [ "$m" = NOPR ]; then inject "$dir" "repos/$OR/commits/$d/pulls" 200 '[]'; return; fi
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$m\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"name\":\"tos-gate\",\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"
  wfcontent "$wfv" > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")"
  # [v2.20 #1(2)] 서버 잡 스텝 기록 — actions/runs/{run_id}/jobs
  inject "$dir" "repos/$OR/actions/runs/424242/jobs" 200 "$(jobs_json "$jv" "$h")"; }
jobs_json(){ # jobs_json <variant> <head>  — ok | noverify | verifyfail | jobfail | norun
  local v="$1" h="$2" steps
  case "$v" in
    ok)         steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]' ;;
    noverify)   steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]' ;;
    verifyfail) steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"failure","number":3}]' ;;
    norun)      steps='[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]' ;;
    jobfail)    steps='[{"name":"tos-gate: run harness","conclusion":"success","number":1},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":2}]' ;;
  esac
  local jc=success; [ "$v" = jobfail ] && jc=failure
  printf '{"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"%s","head_sha":"%s","steps":%s}]}' "$jc" "$h" "$steps"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't84v220_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$WFS" "$EX219" "$CTRL" "$EX218"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 판정 실행기 vs 직전 판 실행기 diff 행수 = %s (v2.20 델타: 구조 파싱 2층 + 격리 스냅샷) --\n' "$(diff "$EX219" "$EX" | grep -c '^[<>]')"
printf 'git version = %s · gh version = %s\n' "$(git --version)" "$(gh --version | head -1)"

########################################################################
sec "A. [C6] 원시 host 프로브 — 심판 실측 프로브 재현 (실행기 밖 · GET-only)"
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api --hostname github.com repos/$OR --jq .default_branch    # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api --hostname github.com "repos/$OR" --jq .default_branch 2>&1 | grep -E '^\* Request to|^> (GET|Host)|^< HTTP|^main' | sed 's/^/  | /'
echo "  ⇒ --hostname 이 GH_HOST 를 이긴다: 요청 host = api.github.com"
echo
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api repos/$OR --jq .default_branch    # (--hostname 없음 = v2.18 거동)  utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api "repos/$OR" --jq .default_branch 2>&1 | grep -E '^\* Request to|^> (GET|Host)|^< HTTP|^\* dial|^error connecting' | sed 's/^/  | /'
echo "  ⇒ host 없는 명령은 GH_HOST 로 간다: https://example.invalid/api/v3/repos/... (심판 프로브 그대로)"

########################################################################
sec "T-84 ⑫-1 live — 기준선(override 없음) · 원격=핀 · 선언=핀 · D=∅"
R="$FX/host-base"; mk "$R"; art "$R" "$OR" main >/dev/null; run "$R" gh "$EX"

sec "T-84 ⑫-2 live — GH_HOST=example.invalid + GH_ENTERPRISE_TOKEN=dummy 로 «실행기 전체»를 돌린다 → 상태값 불변이어야 한다"
run "$R" gh "$EX" "GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy "

sec "T-84 ⑫-3 live — override 하에서 실행기가 실제로 어느 host 로 갔는가 (GH_DEBUG=api 요청 host 캡처)"
echo "  주: 실행기는 gh 의 stderr 를 \$U17_CAPTURE_DIR/<key>.err 로 보내므로 GH_DEBUG 출력은 그 파일에 남는다 — 실행 후 전수 grep 한다."
DBG=$(mktemp -d)
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=$DBG bash u17-verify-v220.sh <fixture>   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
env GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR="$DBG" bash "$EX" "$R" >/dev/null 2>&1; echo "  (u17_rc=$?)"
echo "\$ grep -h '^\* Request to\|^> Host:' $DBG/*.err | sort | uniq -c"
grep -h -E '^\* Request to https|^> Host:' "$DBG"/*.err 2>/dev/null | sed -E 's#^(\* Request to https?://[^/]+)/.*#\1/…#' | sort | uniq -c | sed 's/^/  | /'
echo "  ⇒ 실행기의 «모든» 요청 host = api.github.com (override 무효)"

sec "T-84 ⑫-4 대조군 — «--hostname 제거 + GH_HOST 재핀 제거» 변형(v2.18 거동)을 같은 override 로 실행 → 타 host 로 가서 UNVERIFIABLE 로 접혀야 한다"
run "$R" gh "$CTRL" "GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy "

sec "T-84 ⑫-5 대조군 host 캡처 — 대조군은 실제로 example.invalid 로 나간다"
DBG2=$(mktemp -d)
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=$DBG2 bash u17-verify-v219-CTRL-nohost.sh <fixture>   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
env GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR="$DBG2" bash "$CTRL" "$R" >/dev/null 2>&1; echo "  (u17_rc=$?)"
echo "\$ grep -h '^\* Request to\|^> Host:' $DBG2/*.err | sort | uniq -c"
grep -h -E '^\* Request to https|^> Host:' "$DBG2"/*.err 2>/dev/null | sed -E 's#^(\* Request to https?://[^/]+)/.*#\1/…#' | sort | uniq -c | sed 's/^/  | /'
echo "  ⇒ 대조군은 GH_HOST 가 지정한 타 host(example.invalid/api/v3)로 나가 조회가 전부 실패한다 — 그 host 가 응답을 주면 그 응답이 판정 입력이 된다(위조 표면)"

sec "T-84 ⑫-6 대조군 — override «없이» 같은 대조군 실행 (델타가 override 민감도임을 고정)"
run "$R" gh "$CTRL"

########################################################################
sec "B1. [v2.20 #1(1)] (b)③ 구조 파싱 술어 — 픽스처 8종 직접 실행 (YAML 파서 + 셸 토크나이저 · 실행기 밖 단위 관측)"
WFDIR="$FX/wf"; mkdir -p "$WFDIR"
for v in ok yamlcomment env shcomment trailcomment echoarg ortrue echosha; do
  wfcontent "$v" > "$WFDIR/$v.yml"
done
printf '%-14s %-52s %s\n' "variant" "기대(계약 T-84 ⑬ · (b)③)" "실측"
for v in ok yamlcomment env shcomment trailcomment echoarg ortrue echosha; do
  case "$v" in
    ok)           EXP="BLOB_OK (정상)" ;;
    yamlcomment)  EXP="UNVERIFIED_REVISION (YAML 주석 — 파서가 폐기)" ;;
    env)          EXP="UNVERIFIED_REVISION (env: 값 — run 아님)" ;;
    shcomment)    EXP="UNVERIFIED_REVISION (full-line 셸 주석)" ;;
    trailcomment) EXP="UNVERIFIED_REVISION (trailing 셸 주석 · ⑬b)" ;;
    echoarg)      EXP="UNVERIFIED_REVISION (echo 인자 위치 · ⑬a)" ;;
    ortrue)       EXP="BLOB_OK — «미검출»(⑬c 정직 경계)" ;;
    echosha)      EXP="UNVERIFIED_REVISION (echo <sha> = 비대조)" ;;
  esac
  GOT=$(python3 "$WFS" blob "$WFDIR/$v.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '%-14s %-52s %s\n' "$v" "$EXP" "$GOT"
done
echo
echo "-- 대표 3종의 파싱 원문 (주석 제거 후 토큰·단순 명령 분해까지) --"
for v in ok trailcomment ortrue; do
  echo "== $v =="; sed 's/^/  | /' "$WFDIR/$v.yml"; python3 "$WFS" blob "$WFDIR/$v.yml" 2>&1 | sed 's/^/  /'
done

sec "B2. [v2.20 #1(2)] 서버 잡 steps[] mock — 계약 리터럴 스텝 이름 2종 × conclusion (실행기 밖 단위 관측)"
JD="$FX/jobs"; mkdir -p "$JD"
for v in ok noverify verifyfail norun jobfail; do jobs_json "$v" deadbeef > "$JD/$v.json"; done
printf '%-11s %-46s %s\n' "variant" "기대" "실측"
for v in ok noverify verifyfail norun jobfail; do
  case "$v" in
    ok)         EXP="SERVER_OK" ;;
    noverify)   EXP="UNVERIFIED_REVISION (verify 스텝 부재 · ⑭)" ;;
    verifyfail) EXP="UNVERIFIED_REVISION (verify conclusion=failure · ⑭)" ;;
    norun)      EXP="UNVERIFIED_REVISION (run harness 스텝 부재 · ⑭)" ;;
    jobfail)    EXP="UNVERIFIED_REVISION (잡 conclusion=failure)" ;;
  esac
  GOT=$(python3 "$WFS" server "$JD/$v.json" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '%-11s %-46s %s\n' "$v" "$EXP" "$GOT"
done
echo "-- ok · verifyfail 원문 --"; for v in ok verifyfail; do echo "== $v =="; python3 "$WFS" server "$JD/$v.json" 2>&1 | sed 's/^/  /'; done

########################################################################
sec "C. T-84 ⑬ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · blob 변형만 바뀐다"
RB="$FX/blob"; mk "$RB"; art "$RB" "$OR" main >/dev/null; WB2=$(wf "$RB" ok); DB2=$(d0a "$RB")
echo "W(PR head)=$WB2  d=$DB2"

sec "T-84 ⑬ 기준선 — 정상 워크플로(계약 리터럴 스텝 이름·하니스 실행·sha256 대조) + 서버 스텝 success ⇒ PREVENTION_ACTIVE"
S="$SEAM/b3-ok"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" ok ok; run "$RB" "file:$S"

sec "T-84 ⑬a — 하니스 경로가 «echo 인자» 위치 (실행 아님) ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0"
S="$SEAM/b3-13a"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" echoarg ok; run "$RB" "file:$S"

sec "T-84 ⑬a 판별력 대조 — 같은 seam 을 «두 리터럴 grep» 직전 판 실행기(v2.19)로 실행 → 통과하면 그것이 심판 #1 이 지목한 실패다"
run "$RB" "file:$S" "$EX219"

sec "T-84 ⑬b — sha256 대조가 «trailing 셸 주석» 안에만 있고 실제 run 은 true ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0"
S="$SEAM/b3-13b"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" trailcomment ok; run "$RB" "file:$S"

sec "T-84 ⑬b 판별력 대조 — 같은 seam 을 직전 판 실행기(v2.19)로"
run "$RB" "file:$S" "$EX219"

sec "T-84 ⑬c — «|| true» 런타임 무효화: 대조는 «능동 명령»이라 구조 파싱·서버 스텝 둘 다 통과 ⇒ PREVENTION_ACTIVE = «미검출»(계약이 선언한 정직 경계)"
S="$SEAM/b3-13c"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" ortrue ok; run "$RB" "file:$S"

sec "T-84 ⑬ 추가 변형 — YAML 주석에만 심은 blob ⇒ UNVERIFIED_REVISION"
S="$SEAM/b3-yaml"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" yamlcomment ok; run "$RB" "file:$S"

########################################################################
sec "D. T-84 ⑭ — blob 구조는 «통과»하나 서버 잡 steps[] 에 계약 리터럴 스텝이 부재 ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0"
S="$SEAM/b3-14a"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" ok noverify; run "$RB" "file:$S"

sec "T-84 ⑭ 판별력 대조 — 같은 seam 을 직전 판 실행기(v2.19 · 서버 스텝 미대조)로 → 통과하면 그것이 v2.20 이 닫은 자리다"
run "$RB" "file:$S" "$EX219"

sec "T-84 ⑭-b — verify 스텝 conclusion=failure ⇒ PREVENTION_UNVERIFIED_REVISION"
S="$SEAM/b3-14b"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" ok verifyfail; run "$RB" "file:$S"

sec "T-84 ⑭-c — 게이트 잡 자체가 conclusion=failure ⇒ PREVENTION_UNVERIFIED_REVISION"
S="$SEAM/b3-14c"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DB2" "$WB2" 777001 "$TLAND" ok jobfail; run "$RB" "file:$S"

########################################################################
sec "⑪ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · 이후 (a)~(f) 는 seam 만 바뀐다"
RC="$FX/cont"; mk "$RC"; art "$RC" "$OR" main >/dev/null; WHEAD=$(wf "$RC"); DCOM=$(d0a "$RC")
echo "W(PR head)=$WHEAD  d=$DCOM"

sec "T-84 ⑪-(a) SIMULATED — 정상: 적용 룰셋 created_at·updated_at ≤ t_land($TLAND) → PREVENTION_ACTIVE"
S="$SEAM/a"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(b) SIMULATED — off→merge→on: updated_at(2026-08-11) > t_land($TLAND) → PREVENTION_CONTINUITY_UNVERIFIABLE"
S="$SEAM/b"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-11T09:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(b') 판별력 대조 — 같은 (b) seam 을 «직전 판» 실행기(u17-verify-v218e.sh)로 실행 → 연속성 미소비라 통과해야 한다(= v2.19 가 닫은 자리)"
run "$RC" "file:$S" "$EX218"

sec "회귀 ⑤-a live — 선언 target=비-default 브랜치 → PREVENTION_TARGET_MISMATCH"
R="$FX/decl-wb"; mk "$R"; art "$R" "$OR" "$WB" >/dev/null; run "$R" gh

sec "회귀 ⑤-b live — 선언 owner_repo=octocat/Hello-World → PREVENTION_TARGET_MISMATCH"
R="$FX/decl-oct"; mk "$R"; art "$R" "octocat/Hello-World" main >/dev/null; run "$R" gh

sec "회귀 ⑩-a live — 원격이 타 host 동일 경로(gitlab.com) → PREVENTION_TARGET_MISMATCH"
R="$FX/rem-gitlab"; mk "$R" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; art "$R" "$OR" main >/dev/null; run "$R" gh

sec "회귀 ⑩-b live — 원격이 타 owner(git@github.com:octocat/kis_unified_sts.git) → PREVENTION_TARGET_MISMATCH"
R="$FX/rem-oct"; mk "$R" git@github.com:octocat/kis_unified_sts.git; art "$R" "$OR" main >/dev/null; run "$R" gh

sec "회귀 ⑨-a — P_first→W→d→P_edit (착수 «후» 아티팩트 편집) → PREVENTION_ARTIFACT_MUTATED (전순서 7 < 연속성 9)"
R="$FX/mutated"; mk "$R"; art "$R" "$OR" main >/dev/null; W9=$(wf "$R"); D9=$(d0a "$R")
printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED (edited AFTER d)\n' "$OR" > "$R/$PC"
git -C "$R" add -A; git -C "$R" commit -q -m "P_edit: artifact edited after D0-A start (SIMULATED)"
S="$SEAM/mut"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$D9" "$W9" 777001 "$TLAND"; run "$R" "file:$S"

########################################################################
sec "본 저장소 현행 상태 — live 1회 (GET --hostname github.com) · 격리 스냅샷 기층 위에서"
echo "  HEAD=$(git -C "$REPO" rev-parse HEAD) · .git 크기=$(du -sh "$REPO/.git" | cut -f1) · $(git -C "$REPO" count-objects -vH | grep size-pack)"
T0=$(date +%s)
echo "\$ bash u17-verify-v220.sh $REPO"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; RCL=$?; echo "u17_rc=$RCL"
echo "  [비용 실측] 격리 스냅샷 포함 전체 실행 시간 = $(( $(date +%s) - T0 ))초 (계약 «--no-local 은 판정 1회이므로 감수»의 실측치)"
echo "  [서버 쓰기 0] 이 드라이버의 gh 호출은 전부 \`gh api -i --hostname github.com <GET path>\` 다 — POST/PATCH/PUT/DELETE·설정 변경 0"
```

## 9. 관측 보고 · 결함 후보 (등급 명시)

### M-1 **[fail-open — 실행기 계보 · 계약 문언 아님]** 격리 스냅샷 진입 후 «캐시된 결합 base» 는 거짓 ABSENT 를 만든다

- 첫 실행에서 `gitpath()` 가 실행기 시작 시점의 `--show-toplevel` 을 캐시해 쓰는 바람에, 스냅샷 진입 «후»의 grafts canary 가 **원 저장소 경로**를 검사했다(실측 로그: canary 가 `/Users/…/kis_unified_sts/.git/info/grafts` 를 가리킴).
- 극성: 스냅샷이 오염돼도 canary 가 **부재**로 읽어 통과 = **fail-open**. v2.19 E15 가 성문화한 «거짓 부재가 검사를 통과시키면 fail-open» 의 **재발 형태**이며, 격리 스냅샷(=cwd 이동)이 그 표면을 새로 만든다.
- 처분: 이 증거의 실행기에서 **D-γ 로 수정**(결합 base 를 호출 시점 파생)하고 재실행했다(§2 diff · §6 canary 가 스냅샷 경로를 가리킨다).
- **계약 제안(문언)**: :7115-7119 정직 경계 (b) canary 절에 «스냅샷 안에서 파생 경로를 **재파생**한다(진입 전 값 재사용 금지)» 를 명시. **등급: fail-open(구현 계보) → 문언 보강 제안.**

### M-2 **[관측]** 격리 스냅샷의 실측 비용 = 본 저장소 1회 151초

계약은 «판정 1회이므로 감수»라 적었고 실측이 그 범위를 구체화한다(89M `.git`·2,228 커밋 기준 151초, 픽스처는 1초 미만). 판정이 CI 안에서 반복 호출되는 형태로 바뀌면 재검토가 필요하다는 **비용 관측**이며 현행 문언과 충돌하지 않는다. **등급: 관측.**

### M-3 **[문언 — 계약이 실행과 어긋난 자리]** :5468 «명령 위치(첫 단어)» 는 `bash tools/tos_entry_harness.sh` 를 배제한다

- 계약 `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5468` 은 하니스가 «파이프라인 한 명령의 **«명령 위치»(첫 단어)**에 실재» 해야 한다고 적는다(대비 예시는 `echo "…경로…"`).
- 그러나 워크플로의 관용 표기 `bash tools/tos_entry_harness.sh` 에서 첫 단어는 `bash` 이고 하니스는 **인자**다. 문언을 «문자» 그대로 구현하면 **정상 워크플로가 red** 가 된다(과잉 차단).
- 이 증거의 술어는 «명령 위치 ∪ 인터프리터(`bash|sh|zsh|dash|ksh`·`env`)의 스크립트 인자»로 읽고, 문자 구현 결과를 **판정 미소비 대조 관측**으로 함께 방출한다(`WF-P6x` 라인 — §3-1 원문에서 `ok` 변형이 «첫 단어» 구현으로는 `False`).
- **등급: 문언**(극성은 과잉 차단이므로 fail-open 아님). 제안: :5468 에 «인터프리터의 스크립트 인자도 실행 위치» 를 명시하거나, D0-A 워크플로가 `./tools/tos_entry_harness.sh` 형태를 쓰도록 못박기.

### M-4 **[관측]** ⑬c 는 계약이 예고한 그대로 «미검출» 이다

`shasum … | grep <sha> || true` 는 구조 파싱(대조가 «능동 명령»)과 서버 스텝(이름·`conclusion`) 둘 다 통과해 `PREVENTION_ACTIVE` 가 된다. 계약 :5472-5477 이 «위조 비용을 올리되 닫지 못한다»고 적은 자리와 **정확히 일치**하며, 이 증거는 그 경계를 실행으로 고정했다. **등급: 관측(정직 경계 확인).**

### M-5 **[관측]** 서버 스텝 이름 대조는 «이름» 층이라 `name:` 위조에 열려 있다

blob 파싱이 얻은 스텝 `name:` 과 서버 `steps[]` 이름을 대조하지만, 두 값 모두 **작성자가 정하는 문자열**이다 — 계약 리터럴과 같은 이름을 붙인 «다른 내용»의 스텝은 이름·`conclusion` 층을 통과한다(계약 :5486-5489 이 «GitHub 내부 실행 간극»으로 자인한 그 층과 같다). 이 증거는 그 층을 넘지 않는다. **등급: 관측(자인 경계).**

### M-6 **[fail-open/차단 등급 신규 결함 후보 0 — 계약 문언]**

계약 문언을 그대로 구현했을 때 green 이 되는 새 자리는 이 회차 U-17 축에서 발견되지 않았다. M-1 은 **실행기 계보**의 결함(수정 후 재실행)이고, M-3/N-1(U-16 문서)은 과잉 차단 방향의 문언 결함이다.
