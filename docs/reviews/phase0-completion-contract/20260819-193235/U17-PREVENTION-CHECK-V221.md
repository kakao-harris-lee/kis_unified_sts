# U17-PREVENTION-CHECK-V221 — T-84 실행 증거 (계약 v2.21 동결 `0528a919` · (b)③ «정본 대조»)

- **비규범 부속**(non-normative). 계약·개발계획을 바꾸지 않는다. 판정 권한 없음 — 실행 «기록»이다.
- 생성 UTC: `2026-08-19T12:19:34Z` (드라이버 첫 줄 원문)
- **S-24 결속**(§1 원문): HEAD == `0528a919` · 계약 워킹트리 blob == 동결 blob · 개발계획 blob == 동결 blob · `0528a919..HEAD` 두 문서 커밋 **0** · 하니스 `sed -n '4664,4764p'` sha256 == `957bf49d…`
- 실행기 `u17-verify-v221.sh` sha256 `5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727` (486행) · 정본 대조 술어 `wfcanon-v221.py` sha256 `a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d` (159행) · 픽스처 생성기 `mkwf-v221.py` sha256 `f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5` (79행)
- **운영자 지침 이행**(CLAUDE.md «Development Discipline» — 기존 도구 재사용·바퀴 재발명 금지): YAML 파싱은 **기존 도구 `yq`**, 대조는 **byte 비교**뿐. v2.20 술어의 **자작 셸 토크나이저·명령 위치 판별기는 폐기**했다(§2).
- **GitHub 는 GET-only**(`gh api -i --hostname github.com <GET>`) · 서버 쓰기·설정 변경 **0** · 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용).
- **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다** — 서버 파생 실측은 `x-github-request-id` 와 함께 §10 원문에 있다.

## 1. S-24 결속 원문

```text
s24_v221_utc=2026-08-19T12:19:48Z
HEAD = 0528a9195494f691c77b83126e3d44952fd2d660  (0528a919 와 동일? YES)
계약 워킹트리 blob   = d9d45793fa37b3cb578e76a6051c72b8118f3e5b  == 0528a919 blob d9d45793fa37b3cb578e76a6051c72b8118f3e5b → 동일
개발계획 워킹트리 blob = 4b2f664f835c4f3c68e4dff8560214aaa70f8969  == 0528a919 blob 4b2f664f835c4f3c68e4dff8560214aaa70f8969 → 동일 (v2.21 에서 한 줄 추가·동결본과 동일해야 한다)
0528a919..HEAD 두 문서 커밋 = 0건 · 전체 커밋 = 0건
계약 행수 = 7531 · 개발계획 행수 = 580
하니스 sed -n 4664,4764p sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (계약 리터럴 957bf49d… 일치? YES · 0528a919 과 byte-동일? YES)
워킹트리 두 문서 변경 = 0건
본 저장소 [PARENTS-UNTRUSTED] 관측: replace -l=[] · info/grafts=ABSENT · is_shallow=false
-- 서버 사후 재조회 (GET 1회 · --hostname github.com) --
$ gh api -i --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection    # utc=2026-08-19T12:19:49Z
  | HTTP/2.0 200 OK
  | X-Github-Request-Id: 254A:11185E:CBEA4C:E1B44E:6A859F65
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks
  ⇒ (a) 술어 입력 불변: contexts=["test"] · tos-gate 부재 ⇒ 본 저장소 live 상태값 극성은 v2.20 증거(d101eb63) 와 동일하다
픽스처 격리: scratchpad 독립 저장소 31개 · 본 저장소 worktree 목록 3줄(이 증거는 worktree 0개 생성)
```

## 2. 실행기 파생 — v2.20(에라타 `ae842cce`) → v2.21 (델타 1건)

| 델타 | 계약 근거 | 내용 |
| --- | --- | --- |
| **D-1** | `(b)③` :5467-5510 (#1) | «구조 파싱(자작 토크나이저)» → **«정본 대조»** — 술어 파일 교체(`wfstruct-v220.py` → `wfcanon-v221.py`). 서버 잡 스텝 대조(2)·격리 스냅샷·host 결속·U-17-c 10값은 **코드 델타 0** |

```diff
2c2,7
< # u17-verify (v2.20 동결 3d17ea66) — U-17 «예방 통제 활성 증거» 실행기 (계약 3d17ea66 §12.3.4 U-17)
---
> # u17-verify (v2.21 동결 0528a919) — U-17 «예방 통제 활성 증거» 실행기 (계약 0528a919 §12.3.4 U-17)
> #   v2.20/에라타 ae842cce 실행기(sha256 67d636ce...) 에서 파생 — 델타는 **v2.21 심판 #1 처분 1건**뿐이다:
> #     [(b)3 :5467-5510] «구조 파싱(자작 토크나이저)» -> **«정본 대조»**(YAML 파서 + 정규화 후 byte 비교).
> #       술어 파일 교체: wfstruct-v220.py -> wfcanon-v221.py (자작 셸 토크나이저·명령 위치 판별기 폐기 —
> #       운영자 «바퀴 재발명 금지» 지침·CLAUDE.md Development Discipline).  서버 잡 스텝 대조(2)·격리 스냅샷·
> #       host 결속·U-17-c 10값은 v2.20 거동 그대로(코드 델타 0).
30c35
< WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfstruct-v220.py}"   # [v2.20 #1] 구조 파싱 술어 (YAML 파서·셸 토크나이저)
---
> WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221.py}"   # [v2.21 #1] «정본 대조» 술어 (YAML 파서 + 정규화 후 byte 비교)
419c424
<     # ── [v2.20 #1 (1)] 구조 파싱 — «문자열 존재»가 아니라 «실행 스텝 구조» (정규식·grep 아님)
---
>     # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
425c430
<       UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 구조 파싱 불가(YAML 파서 실패)"; continue ;;
---
>       UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 정본 대조 불가(YAML 파서 실패)"; continue ;;
427c432
<       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 구조 파싱 불충족 — 하니스가 «실행 위치»에 없거나 sha256 이 «대조 피연산자»가 아님 (T-84 ⑬)"; continue ;;
---
>       *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)"; continue ;;
443c448
<     printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
---
>     printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
```

정본 대조 술어의 «관측량»은 다음 셋뿐이다 — ① `yq -o=json` 파싱(기존 도구) ② 계약 정규화 규칙(CRLF→LF · 줄 trailing **ASCII `[ \t]`** 제거 · 빈 줄/full-line 주석 제거 · LF 결합) ③ 정본과의 **byte 비교** + 닫힌 메타 키 집합. 도달성 분석기·AST·정규식 매칭은 **없다**(계약 :5508 «기각 대안» 과 정합).

## 3. 정본 리터럴 결속 — 계약 코드펜스 원문 == 술어 상수

```text
########## A. 정본 리터럴 결속 — 계약 코드펜스 원문 == 술어 CANON_A/B (리터럴 앵커로 추출·행 번호 하드코딩 금지) ##########
  계약 :5476-5477 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  술어 CANON_A          = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'   → byte 동일? True
  계약 :5487-5488 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  술어 CANON_B          = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"   → byte 동일? True
  닫힌 메타 키 집합: 허용 키 ['name', 'run', 'shell'] · shell 정본값 ['bash', 'bash -eo pipefail {0}', 'bash -euo pipefail {0}']

```

→ 정본 A/B 는 **계약 본문의 코드펜스에서 리터럴 앵커로 추출**해 술어 상수와 byte 대조했다(행 번호 하드코딩 없음). **해시·리터럴 발명 0.**

## 4. blob «정본 대조» 배터리 — 22 픽스처 (기대는 생성기가 «미리» 적은 값)

```text
########## B. blob «정본 대조» 배터리 — 픽스처 22종 (실행기 밖 단위 관측 · 기대는 픽스처 생성기가 «미리» 적은 값) ##########
  fixtures=22 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/wf
  id                 기대(계약 T-84 ⑬) 실측                 설명
  pos-canonical      BLOB_OK                BLOB_OK                양성 — 정본 A/B 정확  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK                정규화 대조군 — full-line 주석 + 빈 줄 추가  [OK]
  ctrl-trailing-ws   BLOB_OK                BLOB_OK                정규화 대조군 — trailing 공백/탭  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK                정규화 대조군 — CRLF 줄끝  [OK]
  ctrl-folded        BLOB_OK                BLOB_OK                정규화 대조군 — 스텝 A 를 folded `>` 로 «의미 동일» 표기(빈 줄=줄바꿈 접기)  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬a — 하니스가 echo 인자  [OK]
  13b-trailcomment   UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬b — trailing 주석(정규화가 제거하지 않는다)  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬c — `|| true` 무효화 (v2.20 «미검출» → v2.21 검출)  [OK]
  13d-unreachable    UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬d — 도달 불가 호출 `false && …`  [OK]
  13e-continue       UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — continue-on-error: true  [OK]
  13e-if-always      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — if: always()  [OK]
  13e-extra-key      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — 추가 메타 키(env:) = 닫힌 집합 위배  [OK]
  13f-set-plus-e     UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬f — set +e  [OK]
  13f-trap           UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬f — trap … ERR  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `exit 0`  [OK]
  13g-exec-true      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `exec true`  [OK]
  13g-guarded-exit   UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `[ -n "${SKIP:-}" ] && exit 0`  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION    NBSP trailing (ASCII 핀 — 유니코드 공백은 제거하지 않는다)  [OK]
  inline-semicolon   UNVERIFIED_REVISION    UNVERIFIED_REVISION    inline `;` 한 줄 (허용 정본 집합 1)  [OK]
  env-bash           UNVERIFIED_REVISION    UNVERIFIED_REVISION    `env bash …` (정본 아님)  [OK]
  shell-no-set       UNVERIFIED_REVISION    UNVERIFIED_REVISION    shell: bash -euo pipefail {0} + `set` 줄 없음  [OK]
  ctrl-bom           BLOB_OK                BLOB_OK                정규화 대조군 — UTF-8 BOM 선두  [OK]
  ⇒ 기대와 다른 케이스 = 0 건

-- 대표 4종 파싱·정규화 원문 (양성 · 정규화 대조군 · ⑬g · NBSP) --
== pos-canonical ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== ctrl-comments ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           # lead comment
  |           set -euo pipefail
  | 
  |           bash tools/tos_entry_harness.sh
  |           # trailer
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = '# lead comment\nset -euo pipefail\n\nbash tools/tos_entry_harness.sh\n# trailer\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== 13g-exit0 ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           exit 0
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = False  ← 첫 불일치 오프셋 18
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== nbsp-trailing ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail 
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\xa0\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\xa0\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = False  ← 첫 불일치 오프셋 17
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

```

## 5. 서버 잡 `steps[]` mock — ⑭

```text
########## C. 서버 잡 steps[] mock — ⑭ (계약 리터럴 스텝 이름 × conclusion) ##########
  variant     기대                                         실측
  ok          SERVER_OK                                      SERVER_OK
  noverify    UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  verifyfail  UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  norun       UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  jobfail     UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION

```

## 6. e2e (실행기 전체 · SIMULATED seam) — 기대/실측

| # | 구성 | 실행기 | 계약 기대 | 실측 | rc | 일치 |
| --- | --- | --- | --- | --- | --- | --- |
| D-1 | 정본 A/B 정확 | v2.21 | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 | ✅ |
| D-2 | **⑬g 선행 종결자 `exit 0`** | v2.21 | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 | ✅ |
| D-3 | 같은 seam | **v2.20(구조 파싱)** | (닫은 자리 실증) | **`PREVENTION_ACTIVE`** | **0** | ✅ 회피 실증 |
| D-4 | **⑬c `\|\| true`** | v2.21 | `UNVERIFIED_REVISION`(v2.20 «미검출» 뒤집힘) | **`PREVENTION_UNVERIFIED_REVISION`** | 1 | ✅ |
| D-5 | 같은 seam | **v2.20** | (v2.20 은 미검출) | **`PREVENTION_ACTIVE`** | **0** | ✅ 실증 |
| D-6 | 정규화 대조군(주석·빈 줄) | v2.21 | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 | ✅ |
| D-7 | 정본 일치 + **⑭ 서버 스텝 부재** | v2.21 | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 | ✅ |

## 7. 정본 B 런타임 실증 — 계약이 «구조로 보장»한다고 적은 실패 전파

```text
########## E. 정본 B 런타임 실증 — 계약이 «구조로 보장»한다고 적은 실패 전파를 실제로 돌린다 ##########
  픽스처 하니스 파일 sha256 = dd09dcd1a77e1ad3a89d220e2de8feefb72419696589c55f727c42ed1ab44bb1  (계약 결속값 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 와는 다르다 — 여기서는 «정본 B 의 형식»이 실패를 전파하는지만 본다)
  $ printf '%s  tools/tos_entry_harness.sh\n' <sha> | shasum -a 256 -c -    # 두 칸 공백 포맷
  | tools/tos_entry_harness.sh: OK
  정상 rc=0
  | tools/tos_entry_harness.sh: FAILED
  | shasum: WARNING: 1 computed checksum did NOT match
  변조(기대 sha 불일치) rc=1
  ⇒ 정본 B 는 sha 불일치에서 shasum -c 가 비-0 → set -euo pipefail 로 스텝 실패(계약 :5491 서술과 일치)

```

→ **정상 `OK`/rc 0 · 변조 `FAILED`/rc 1** — 계약 :5491 의 «sha 불일치 시 `shasum -c` 비-0 → `set -euo pipefail` 로 스텝 실패» 서술과 일치. 두 칸 공백 포맷(`printf '%s  <path>\n'`)도 그대로 실행했다.

## 8. 회귀 (기대/실측)

| # | 케이스 | 기대 | 실측 | rc |
| --- | --- | --- | --- | --- |
| F-1 | ⑪-(a) 연속성 정상 (SIMULATED) | `PREVENTION_ACTIVE` | `PREVENTION_ACTIVE` | 0 ✅ |
| F-2 | ⑪-(b) 룰셋 `updated_at > t_land` | `CONTINUITY_UNVERIFIABLE` | `PREVENTION_CONTINUITY_UNVERIFIABLE` | 1 ✅ |
| F-3 | ⑫ live · `GH_HOST` override 유/무 | 상태 불변 | `PREVENTION_INSUFFICIENT` → `PREVENTION_INSUFFICIENT` | 1/1 ✅ |
| F-4 | ⑤-a 선언 target=비-default | `TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 ✅ |
| F-5 | ⑤-b 선언 owner_repo=`octocat/Hello-World` | `TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 ✅ |
| F-6 | ⑩-a 원격 타 host(gitlab.com) | `TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 ✅ |
| F-7 | ⑩-b 원격 타 owner | `TARGET_MISMATCH` | `PREVENTION_TARGET_MISMATCH` | 1 ✅ |
| F-8 | ⑨-a 착수 «후» 아티팩트 편집 | `ARTIFACT_MUTATED` | `PREVENTION_ARTIFACT_MUTATED` | 1 ✅ |

## 9. #2 실측 — 비순환 생산 순서 (리터럴 원문 병기 · live 1회 · 순서 SIMULATED)

```text
########## G. #2 실측 — 비순환 생산 순서 (계약·개발계획 리터럴 원문 병기) ##########
-- (1) UNCHK-008 레지스터 행 (owner_track 열) — 리터럴 앵커로 찾는다 --
  계약 :6228  owner_track=« `Phase 0` » · closable=« `YES` »
  본문 발췌: [v2.21 — 심판 #2] 이 축의 도입(룰셋 required check·`.github/workflows/tos-gate.yml`·하니스 파일 실체화)은 D0-A 착수 «전» 운영자/인프라 선행 단계이며 U-17 이 live 검증한다 — �
-- (2) 산문 2곳 (v2.21 전파) --
  4985:예방(진입 표면 거부)   **`UNCHK-008` 소관**(`Phase 0` — **[v2.21]** D0-A 착수 전 선행조건·운영자/인프라) — 브랜치 보호·훅은
  5112:          **닫지 못하는 것**: **근면한 세탁**. **예방은 `UNCHK-008`(`Phase 0` — **[v2.21]** D0-A 선행조건)**
-- (3) U-17 하니스 «pre-D0-A 실체화» 리터럴 --
  213:| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`fals
  4404:| **#2 #5/#6 비순환 생산 순서** (medium) | UNCHK-008 `owner_track=Phase 1`·U-17 하니스 «D0-A 산출물» — Phase 0 소비 전 산출·폐쇄 주체 단일 비순환 순서 부재 | **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 선행조건·운영자/인프라·산문 2곳 전파) · **U-17 하니스 «D0-A 산출물»→
  4480:②′ **[v2.21 — 심판 #2 연장]** ②의 예방 통제 불릿에 **하니스 파일 실체화**를 같은 선행조건으로 추가 — **운영자 승인 (D) 개정의 «연장»**(같은 대상·같은 pre-D0-A 주체·시점: UNCHK-008 `owner_track=Phase 0`·U-17 하니스 «pre-D0-A 실체화»와 정합):
  5480:                             (경로 리터럴은 계약이 정한다 · **[v2.21 — 심판 #2] 하니스 «파일»은 «pre-D0-A 실체화»** —
  6228:| UNCHK-008 | **저장소 밖 강제 표면** — CI 필수 잡(required check) · **[v2.13] 진입 표면 거부**(브랜치 보호·pre-receive/pre-commit 훅) | 브랜치 보호 설정이라 저장소 내 파일로 증명 불가. `tos-firewall.yml`도 "NOT configured here"를 자인 | GitHub 브랜치 보호 설정 + 증거 보존 (상위 `TOS-
-- (4) 개발계획 Phase 0 선행 조건 불릿 (하니스 파일 실체화 포함) --
  :270  선행 조건 (D0-A 착수 전):
  :271  
  :272  - **예방 통제 활성**: tos-gate required check(룰셋 — `required_status_checks.checks[].app_id`
  :273    == Actions app id)·`.github/workflows/tos-gate.yml`(하니스 `tools/tos_entry_harness.sh`
  :274    경로·sha256 검증 스텝 포함) **및 그 하니스 파일 `tools/tos_entry_harness.sh` 의
  :275    실체화(계약 §12.3.4-R 블록 결속값 sha 957bf49d…)** 도입 → D0-A 착수 전 `PREVENTION_ACTIVE`(계약 §12.3.4 `U-17`).
  :276  
  :277  종료 조건:
-- (5) 본 저장소 현행 실물 — 아티팩트·워크플로·하니스 파일 --
  tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md 부재
  .github/workflows/tos-gate.yml                                 부재
  tools/tos_entry_harness.sh                                     부재
  config/tos_completion.yaml                                     부재
-- (6) 본 저장소 live U-17 상태 (GET · 실행기 1회) --
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1wWud2eY88
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:22:57Z  http=200  x-github-request-id=666A:21B9D:CB06E3:E0EA74:6A85A020
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:22:58Z  http=200  x-github-request-id=0938:177308:C98DD8:DF6E6E:6A85A021
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
  u17_rc=1

```

### 9-1. 순서 실증 (SIMULATED)

```text
########## G-2 순서 실증(SIMULATED) — «아티팩트 + 하니스 파일 실체화 + 룰셋 캡처» 가 D0-A 산출물 «없이» 성립하면 PREVENTION_ACTIVE 에 도달한다 ##########
  커밋 순서:
    983b7c3 seed
    319e2bf pre-D0-A: materialize tools/tos_entry_harness.sh (operator/infra)
    e15c660 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
    9d67dbe W: add .github/workflows/tos-gate.yml (SIMULATED)
  D0-A 산출물(config/tos_completion.yaml) 존재? NO ← D0-A 미착수 · D = ∅
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 9d67dbe 2026-08-19T21:22:59+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * e15c660 2026-08-19T21:22:59+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 319e2bf 2026-08-19T21:22:59+09:00 pre-D0-A: materialize tools/tos_entry_harness.sh (operator/infra)
  * 983b7c3 2026-08-19T21:22:59+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A/.git/info/grafts=no · is_shallow=false · entry HEAD=9d67dbe540961c1d25e150a402ced8bf440a963f
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=9d67dbe540961c1d25e150a402ced8bf440a963f · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.bGaNK2Qj1r
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:23:00Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:23:01Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[e15c660d4dcacb58038a3184c6da4170e6df89d7 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[e15c660d4dcacb58038a3184c6da4170e6df89d7 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=0) ∧ (α) 연속성 성립(t_land=∅) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre
u17_rc=0
  ⇒ 정직 경계: 이 픽스처는 «순서»(pre-D0-A 실체화 → D0-A 착수)만 실증한다 — 실환경 룰셋·워크플로 도입은 인프라/운영자 소관이며 이 증거가 대신하지 않는다
```

→ **정직 경계**: 이 픽스처는 «pre-D0-A 실체화(아티팩트 + 하니스 파일 + 룰셋 캡처) → D0-A 착수» 라는 **순서가 성립 가능함**만 실증한다(D0-A 산출물 `config/tos_completion.yaml` 부재·`D=∅` 상태에서 `PREVENTION_ACTIVE`/rc 0 도달). **실환경의 룰셋·워크플로·하니스 파일 도입은 인프라/운영자 소관**이며 이 증거가 대신하지 않는다 — 본 저장소 현행은 네 산출물 **전부 부재**이고 live 상태는 `PREVENTION_ABSENT` 다.

## 10. 실행 기록 (stdout 전문 · rc·`x-github-request-id` 포함)

### 10-1. `bash t84v221.sh` (1568행)

```text
t84v221_utc=2026-08-19T12:19:34Z
sha256(u17-verify-v221.sh)=5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727
sha256(wfcanon-v221.py)=a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d
sha256(u17-verify-v220.sh)=67d636ce4ac4ff0b4a3da06d24b5551748c7408d3325aebd9f5ac56b264ed101
sha256(mkwf-v221.py)=f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5
-- 판정 실행기 vs 직전 판(v2.20) diff 행수 = 17 (델타: 술어 파일 교체 1건) --
git=git version 2.38.0 · gh=gh version 2.93.0 (2026-05-27) · yq=yq (https://github.com/mikefarah/yq/) version v4.48.1 · python3=Python 3.14.7

########## A. 정본 리터럴 결속 — 계약 코드펜스 원문 == 술어 CANON_A/B (리터럴 앵커로 추출·행 번호 하드코딩 금지) ##########
  계약 :5476-5477 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  술어 CANON_A          = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'   → byte 동일? True
  계약 :5487-5488 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  술어 CANON_B          = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"   → byte 동일? True
  닫힌 메타 키 집합: 허용 키 ['name', 'run', 'shell'] · shell 정본값 ['bash', 'bash -eo pipefail {0}', 'bash -euo pipefail {0}']

########## B. blob «정본 대조» 배터리 — 픽스처 22종 (실행기 밖 단위 관측 · 기대는 픽스처 생성기가 «미리» 적은 값) ##########
  fixtures=22 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/wf
  id                 기대(계약 T-84 ⑬) 실측                 설명
  pos-canonical      BLOB_OK                BLOB_OK                양성 — 정본 A/B 정확  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK                정규화 대조군 — full-line 주석 + 빈 줄 추가  [OK]
  ctrl-trailing-ws   BLOB_OK                BLOB_OK                정규화 대조군 — trailing 공백/탭  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK                정규화 대조군 — CRLF 줄끝  [OK]
  ctrl-folded        BLOB_OK                BLOB_OK                정규화 대조군 — 스텝 A 를 folded `>` 로 «의미 동일» 표기(빈 줄=줄바꿈 접기)  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬a — 하니스가 echo 인자  [OK]
  13b-trailcomment   UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬b — trailing 주석(정규화가 제거하지 않는다)  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬c — `|| true` 무효화 (v2.20 «미검출» → v2.21 검출)  [OK]
  13d-unreachable    UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬d — 도달 불가 호출 `false && …`  [OK]
  13e-continue       UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — continue-on-error: true  [OK]
  13e-if-always      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — if: always()  [OK]
  13e-extra-key      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬e — 추가 메타 키(env:) = 닫힌 집합 위배  [OK]
  13f-set-plus-e     UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬f — set +e  [OK]
  13f-trap           UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬f — trap … ERR  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `exit 0`  [OK]
  13g-exec-true      UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `exec true`  [OK]
  13g-guarded-exit   UNVERIFIED_REVISION    UNVERIFIED_REVISION    ⑬g — 선행 종결자 `[ -n "${SKIP:-}" ] && exit 0`  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION    NBSP trailing (ASCII 핀 — 유니코드 공백은 제거하지 않는다)  [OK]
  inline-semicolon   UNVERIFIED_REVISION    UNVERIFIED_REVISION    inline `;` 한 줄 (허용 정본 집합 1)  [OK]
  env-bash           UNVERIFIED_REVISION    UNVERIFIED_REVISION    `env bash …` (정본 아님)  [OK]
  shell-no-set       UNVERIFIED_REVISION    UNVERIFIED_REVISION    shell: bash -euo pipefail {0} + `set` 줄 없음  [OK]
  ctrl-bom           BLOB_OK                BLOB_OK                정규화 대조군 — UTF-8 BOM 선두  [OK]
  ⇒ 기대와 다른 케이스 = 0 건

-- 대표 4종 파싱·정규화 원문 (양성 · 정규화 대조군 · ⑬g · NBSP) --
== pos-canonical ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== ctrl-comments ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           # lead comment
  |           set -euo pipefail
  | 
  |           bash tools/tos_entry_harness.sh
  |           # trailer
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = '# lead comment\nset -euo pipefail\n\nbash tools/tos_entry_harness.sh\n# trailer\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = True
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = BLOB_OK
  RESULT=BLOB_OK
== 13g-exit0 ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           exit 0
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = False  ← 첫 불일치 오프셋 18
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION
== nbsp-trailing ==
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail 
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\xa0\nbash tools/tos_entry_harness.sh\n'
  WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\xa0\nbash tools/tos_entry_harness.sh'
  WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  WF-C4 [A/run harness] byte 일치    = False  ← 첫 불일치 오프셋 17
  WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = True
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

########## C. 서버 잡 steps[] mock — ⑭ (계약 리터럴 스텝 이름 × conclusion) ##########
  variant     기대                                         실측
  ok          SERVER_OK                                      SERVER_OK
  noverify    UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  verifyfail  UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  norun       UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION
  jobfail     UNVERIFIED_REVISION (⑭)                      UNVERIFIED_REVISION

########## D. e2e — 픽스처 저장소(P → W → d) · seam 의 blob 만 바꾼다 ##########
  W(PR head)=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  d=57aec3cd950e6a87979182c8d810761ada6c6d44

########## D-1 양성 — 정본 A/B 정확 ⇒ PREVENTION_ACTIVE + rc 0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pos bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.coj4EslwJM/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.coj4EslwJM/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pos capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.5WDlJ0eyn2
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pos — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.coj4EslwJM/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.coj4EslwJM/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:37Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:37Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:37Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:37Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:37Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:37Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.coj4EslwJM/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:38Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:38Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:38Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:38Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:39Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=441):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:19:39Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 1619cb7b06bcf5e0c72abe54fd5d14ce40918955:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pos
u17_rc=0

########## D-2 ⑬g 선행 종결자  ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0 bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.R8Huf2XzWG/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.R8Huf2XzWG/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ANwaK0Pu7M
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0 — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.R8Huf2XzWG/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.R8Huf2XzWG/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:40Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:40Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:40Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:40Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:40Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:40Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.R8Huf2XzWG/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:41Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:41Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:41Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:42Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:42Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "8a848a7e1db6a6d61fc2ce90b7c10d1a0beb1bf8", "size": 458, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGV4aXQgMAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=458):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           exit 0
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = False  ← 첫 불일치 오프셋 18
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## D-3 ⑬g 판별력 대조 — 같은 seam 을 «구조 파싱» v2.20 실행기로 → ACTIVE 면 그것이 v2.21 이 닫은 자리(심판 «회피» 지적의 실증) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0b bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BGUztEE9Rg/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BGUztEE9Rg/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.h1DIHlnkkh
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BGUztEE9Rg/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BGUztEE9Rg/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:43Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:43Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:44Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:44Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:44Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:44Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.BGUztEE9Rg/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:44Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:45Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:45Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:45Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:45Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "8a848a7e1db6a6d61fc2ce90b7c10d1a0beb1bf8", "size": 458, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGV4aXQgMAogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAtIG5hbWU6ICJ0b3MtZ2F0ZTogdmVyaWZ5IGhhcm5lc3Mgc2hhMjU2IgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIHByaW50ZiAnJXMgIHRvb2xzL3Rvc19lbnRyeV9oYXJuZXNzLnNoXG4nIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQgfCBzaGFzdW0gLWEgMjU2IC1jIC0=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=458):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           exit 0
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh\n'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['set', '-euo', 'pipefail', 'exit', '0', 'bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['set', '-euo', 'pipefail'], ['exit', '0'], ['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['set', '-euo', 'pipefail', 'printf', '%s  tools/tos_entry_harness.sh\\n', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d', 'shasum', '-a', '256', '-c', '-']
  | WF-P5 [verify] 단순 명령 분해 = [['set', '-euo', 'pipefail'], ['printf', '%s  tools/tos_entry_harness.sh\\n', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'], ['shasum', '-a', '256', '-c', '-']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (shasum -c 체크섬 대조)
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:19:45Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 1619cb7b06bcf5e0c72abe54fd5d14ce40918955:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/g-exit0b
u17_rc=0
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t84v221.sh: command substitution: line 181: syntax error near unexpected token `||'
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t84v221.sh: command substitution: line 181: `|| true'

########## D-4 ⑬c  ⇒ UNVERIFIED_REVISION (v2.20 «미검출» 기대가 뒤집힌 자리) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrue bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.D2lJCE8BMn/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.D2lJCE8BMn/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrue capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.nTwSpPluAc
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrue — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.D2lJCE8BMn/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.D2lJCE8BMn/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:47Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:47Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:47Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:47Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:47Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:47Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.D2lJCE8BMn/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:48Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:48Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:48Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:48Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:48Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "2011c1bc50beaa2ac3b38a3bb07ca6b67eaf8dae", "size": 449, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAtIHx8IHRydWU=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=449):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c - || true
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c - || true\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c - || true"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = False  ← 첫 불일치 오프셋 145
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## D-5 ⑬c 판별력 대조 — v2.20 실행기 (미검출 = ACTIVE 였음을 실증) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrueb bash u17-verify-v220.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GpaFXqNqkq/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GpaFXqNqkq/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrueb capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dBilJcpahS
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrueb — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GpaFXqNqkq/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GpaFXqNqkq/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:50Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:50Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:50Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:50Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:50Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:50Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.GpaFXqNqkq/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:51Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:51Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:51Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:51Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:51Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "2011c1bc50beaa2ac3b38a3bb07ca6b67eaf8dae", "size": 449, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAtIHx8IHRydWU=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=449):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c - || true
  | WF-P0 YAML 파서 = yq -o=json (진짜 파서 · 주석 폐기) · 대상 = jobs.tos-gate.steps[] · 소비 필드 = run: «뿐»
  | WF-P1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-P2 [run] run: 원문 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-P3 [run] bash -n rc=0 
  | WF-P4 [run] 주석 제거 후 토큰 = ['set', '-euo', 'pipefail', 'bash', 'tools/tos_entry_harness.sh']
  | WF-P5 [run] 단순 명령 분해 = [['set', '-euo', 'pipefail'], ['bash', 'tools/tos_entry_harness.sh']]
  | WF-P6 [run] 하니스 실행 판정 = True (인터프리터 실행 = bash tools/tos_entry_harness.sh)
  | WF-P6x [run] «첫 단어» 문자 구현 대조 관측(판정 미소비) = False (실행 위치(명령·인터프리터 스크립트 인자)에 tools/tos_entry_harness.sh 부재)
  | WF-P2 [verify] run: 원문 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c - || true\n"
  | WF-P3 [verify] bash -n rc=0 
  | WF-P4 [verify] 주석 제거 후 토큰 = ['set', '-euo', 'pipefail', 'printf', '%s  tools/tos_entry_harness.sh\\n', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d', 'shasum', '-a', '256', '-c', '-', 'true']
  | WF-P5 [verify] 단순 명령 분해 = [['set', '-euo', 'pipefail'], ['printf', '%s  tools/tos_entry_harness.sh\\n', '957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d'], ['shasum', '-a', '256', '-c', '-'], ['true']]
  | WF-P6 [verify] sha256 능동 대조 판정 = True (shasum -c 체크섬 대조)
  | WF-P7 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:19:52Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 1619cb7b06bcf5e0c72abe54fd5d14ce40918955:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 구조 파싱(2 스텝)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/c-ortrueb
u17_rc=0

########## D-6 정규화 대조군 e2e — 주석·빈 줄만 다른 blob ⇒ 여전히 PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/ctrl bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aJaWVAodQz/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aJaWVAodQz/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/ctrl capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gaCX9xnI6P
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/ctrl — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aJaWVAodQz/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aJaWVAodQz/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:53Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:53Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:53Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:53Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:53Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:54Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.aJaWVAodQz/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:54Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:54Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:54Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:55Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:55Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "ee1daf6bf3cdd2bc09d8fa6e891c43c0d2f34a73", "size": 487, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgIyBsZWFkIGNvbW1lbnQKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCgogICAgICAgICAgYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAogICAgICAgICAgIyB0cmFpbGVyCiAgICAgIC0gbmFtZTogInRvcy1nYXRlOiB2ZXJpZnkgaGFybmVzcyBzaGEyNTYiCiAgICAgICAgcnVuOiB8CiAgICAgICAgICBzZXQgLWV1byBwaXBlZmFpbAogICAgICAgICAgcHJpbnRmICclcyAgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2hcbicgOTU3YmY0OWRhOGZjNmFlMzlmOTdhYmU2Nzk0MTFhZmVhYTVhNTlmNzA3ZjM1YmYzYjNhOGM2ZjlkZTE0MWYwZCB8IHNoYXN1bSAtYSAyNTYgLWMgLQ==\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=487):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           # lead comment
  |           set -euo pipefail
  | 
  |           bash tools/tos_entry_harness.sh
  |           # trailer
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = '# lead comment\nset -euo pipefail\n\nbash tools/tos_entry_harness.sh\n# trailer\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:19:55Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 1619cb7b06bcf5e0c72abe54fd5d14ce40918955:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/ctrl
u17_rc=0

########## D-7 ⑭ 서버 스텝 부재 (blob 은 정본 일치) ⇒ UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 57aec3c 2026-08-19T21:19:36+09:00 D0-A: introduce config/tos_completion.yaml
  * 1619cb7 2026-08-19T21:19:36+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d932084 2026-08-19T21:19:35+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * e66fd3b 2026-08-19T21:19:35+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/s14 bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ftZiE6VdBy/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=57aec3cd950e6a87979182c8d810761ada6c6d44 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ftZiE6VdBy/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/s14 capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.gMuWnqKSwI
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/s14 — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ftZiE6VdBy/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ftZiE6VdBy/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:19:57Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:19:57Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:19:57Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:19:57Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:19:57Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:19:57Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[d9320848ae7ca52d846e9f5454b3ae142c14d74e ] |D|=1 D=[57aec3cd950e6a87979182c8d810761ada6c6d44 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ftZiE6VdBy/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/57aec3cd950e6a87979182c8d810761ada6c6d44/pulls  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/1619cb7b06bcf5e0c72abe54fd5d14ce40918955/check-runs  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=1619cb7b06bcf5e0c72abe54fd5d14ce40918955  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@1619cb7b06bcf5e0c72abe54fd5d14ce40918955 (encoding=base64 size=441):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:19:58Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"1619cb7b06bcf5e0c72abe54fd5d14ce40918955","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success')]
  | WF-S4 스텝 이름 «tos-gate: verify harness sha256» 서버 부재 → UNVERIFIED_REVISION (T-84 ⑭)
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=57aec3cd950e6a87979182c8d810761ada6c6d44 head=1619cb7b06bcf5e0c72abe54fd5d14ce40918955 서버 잡 스텝 대조 실패 — 계약 리터럴 스텝 이름 부재 또는 conclusion≠success (T-84 ⑭) [수집 1건 중 전순서 최소]
u17_rc=1

########## E. 정본 B 런타임 실증 — 계약이 «구조로 보장»한다고 적은 실패 전파를 실제로 돌린다 ##########
  픽스처 하니스 파일 sha256 = dd09dcd1a77e1ad3a89d220e2de8feefb72419696589c55f727c42ed1ab44bb1  (계약 결속값 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d 와는 다르다 — 여기서는 «정본 B 의 형식»이 실패를 전파하는지만 본다)
  $ printf '%s  tools/tos_entry_harness.sh\n' <sha> | shasum -a 256 -c -    # 두 칸 공백 포맷
  | tools/tos_entry_harness.sh: OK
  정상 rc=0
  | tools/tos_entry_harness.sh: FAILED
  | shasum: WARNING: 1 computed checksum did NOT match
  변조(기대 sha 불일치) rc=1
  ⇒ 정본 B 는 sha 불일치에서 shasum -c 가 비-0 → set -euo pipefail 로 스텝 실패(계약 :5491 서술과 일치)

########## F-1 회귀 ⑪-(a) SIMULATED — 연속성 정상 ⇒ PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 28a79e2 2026-08-19T21:19:59+09:00 D0-A: introduce config/tos_completion.yaml
  * 9af8daf 2026-08-19T21:19:59+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 96e48c3 2026-08-19T21:19:59+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 44d9313 2026-08-19T21:19:59+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11a bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont/.git/info/grafts=no · is_shallow=false · entry HEAD=28a79e2bab3e44e550dc49688661412ac5ae19d5
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CHWvnS2TTa/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=28a79e2bab3e44e550dc49688661412ac5ae19d5 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CHWvnS2TTa/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.XMjvOEZ2Gu
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CHWvnS2TTa/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CHWvnS2TTa/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:00Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:00Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:01Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:01Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:01Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:20:01Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[96e48c368d31f9acb78b57c4aad96055d6368314 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[96e48c368d31f9acb78b57c4aad96055d6368314 ] |D|=1 D=[28a79e2bab3e44e550dc49688661412ac5ae19d5 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CHWvnS2TTa/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/28a79e2bab3e44e550dc49688661412ac5ae19d5/pulls  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/9af8daf93fd16d384d767b68b317f80dc919c3e1/check-runs  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=9af8daf93fd16d384d767b68b317f80dc919c3e1  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@9af8daf93fd16d384d767b68b317f80dc919c3e1 (encoding=base64 size=441):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:20:02Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 9af8daf93fd16d384d767b68b317f80dc919c3e1:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=28a79e2bab3e44e550dc49688661412ac5ae19d5 head=9af8daf93fd16d384d767b68b317f80dc919c3e1 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11a
u17_rc=0

########## F-2 회귀 ⑪-(b) SIMULATED — 룰셋 updated_at > t_land ⇒ PREVENTION_CONTINUITY_UNVERIFIABLE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 28a79e2 2026-08-19T21:19:59+09:00 D0-A: introduce config/tos_completion.yaml
  * 9af8daf 2026-08-19T21:19:59+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 96e48c3 2026-08-19T21:19:59+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 44d9313 2026-08-19T21:19:59+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11b bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont/.git/info/grafts=no · is_shallow=false · entry HEAD=28a79e2bab3e44e550dc49688661412ac5ae19d5
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.s8cP4HbbY5/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=28a79e2bab3e44e550dc49688661412ac5ae19d5 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.s8cP4HbbY5/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yMU11ja7tW
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/11b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.s8cP4HbbY5/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.s8cP4HbbY5/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/cont/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:04Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:04Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:04Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:04Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:04Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:20:04Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[96e48c368d31f9acb78b57c4aad96055d6368314 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[96e48c368d31f9acb78b57c4aad96055d6368314 ] |D|=1 D=[28a79e2bab3e44e550dc49688661412ac5ae19d5 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.s8cP4HbbY5/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/28a79e2bab3e44e550dc49688661412ac5ae19d5/pulls  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/9af8daf93fd16d384d767b68b317f80dc919c3e1/check-runs  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=9af8daf93fd16d384d767b68b317f80dc919c3e1  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@9af8daf93fd16d384d767b68b317f80dc919c3e1 (encoding=base64 size=441):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:20:05Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"9af8daf93fd16d384d767b68b317f80dc919c3e1","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 9af8daf93fd16d384d767b68b317f80dc919c3e1:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=28a79e2bab3e44e550dc49688661412ac5ae19d5 head=9af8daf93fd16d384d767b68b317f80dc919c3e1 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님)
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=(α) ruleset 42 updated_at=2026-08-11T09:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가 — 운영자 재심사 경로(영구 차단 아님) [수집 1건 중 전순서 최소]
u17_rc=1

########## F-3 회귀 ⑫ live — GH_HOST override 하 상태 불변 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * a66ae5a 2026-08-19T21:20:06+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 6f52ed9 2026-08-19T21:20:06+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host/.git/info/grafts=no · is_shallow=false · entry HEAD=a66ae5afe3cdb7653b97915db309b47e5b259579
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MM0atKI4X8/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=a66ae5afe3cdb7653b97915db309b47e5b259579 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MM0atKI4X8/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MEZVGAWC97
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MM0atKI4X8/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MM0atKI4X8/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:08Z  http=200  x-github-request-id=F9C1:1DEFCF:C890D2:DE5FE2:6A859F77
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:08Z  http=200  x-github-request-id=B103:C76AD:C888C6:DE5246:6A859F78  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:09Z  http=200  x-github-request-id=331B:11185E:CBFA43:E1C688:6A859F78
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:09Z  http=200  x-github-request-id=CFCA:389700:C5AF95:DB7C6A:6A859F79
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:10Z  http=200  x-github-request-id=6CE0:177308:C8F9D8:DEC5A8:6A859F7A
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:10Z  http=200  x-github-request-id=BB7F:177308:C8FA52:DEC63E:6A859F7A
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[a66ae5afe3cdb7653b97915db309b47e5b259579 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[a66ae5afe3cdb7653b97915db309b47e5b259579 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.MM0atKI4X8/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * a66ae5a 2026-08-19T21:20:06+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 6f52ed9 2026-08-19T21:20:06+09:00 seed
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host/.git/info/grafts=no · is_shallow=false · entry HEAD=a66ae5afe3cdb7653b97915db309b47e5b259579
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zVcGCs5zZO/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=a66ae5afe3cdb7653b97915db309b47e5b259579 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zVcGCs5zZO/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.3niGJi8K5a
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zVcGCs5zZO/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zVcGCs5zZO/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/host/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:13Z  http=200  x-github-request-id=FF0B:346330:C737C1:DD0082:6A859F7C
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:13Z  http=200  x-github-request-id=A3A5:328E21:C8C420:DE8DA3:6A859F7D  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:14Z  http=200  x-github-request-id=C930:335F3A:C7C493:DD923E:6A859F7E
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:14Z  http=200  x-github-request-id=8D76:1D7032:82DCB:970D6:6A859F7E
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:15Z  http=200  x-github-request-id=256A:201076:C80373:DDD094:6A859F7F
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:15Z  http=200  x-github-request-id=B323:21B9D:CA7D38:E04CD6:6A859F7F
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[a66ae5afe3cdb7653b97915db309b47e5b259579 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[a66ae5afe3cdb7653b97915db309b47e5b259579 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.zVcGCs5zZO/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## F-4 회귀 ⑤-a live — 선언 target=비-default 브랜치 ⇒ PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 61e61ee 2026-08-19T21:20:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c28a173 2026-08-19T21:20:16+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-wb/.git/info/grafts=no · is_shallow=false · entry HEAD=61e61eea2cb78bbd096e7b4db2117322ad8099fb
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-wb /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oRTdHgy2CM/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=61e61eea2cb78bbd096e7b4db2117322ad8099fb · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oRTdHgy2CM/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.PnsknSjUyJ
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oRTdHgy2CM/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oRTdHgy2CM/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-wb/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:18Z  http=200  x-github-request-id=09D9:328E21:C8C844:DE92B4:6A859F81
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:18Z  http=200  x-github-request-id=EC38:328E21:C8C8B3:DE9332:6A859F82  (.default_branch=main)
U17-T declared-vs-pin:  target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:19Z  http=200  x-github-request-id=FBE1:177308:C9021A:DECF11:6A859F83
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:20Z  http=200  x-github-request-id=CAA4:11185E:CC03DF:E1D1C1:6A859F83
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:20Z  http=200  x-github-request-id=DFEF:198918:C8AEE1:DE7BB5:6A859F84
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:21Z  http=200  x-github-request-id=31D1:335F3A:C7CA0F:DD9890:6A859F84
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[61e61eea2cb78bbd096e7b4db2117322ad8099fb ] P_last(집합·|1|·blob=4721862ccfb97aa7352a29a7ee9f1c2d16d145ad)=[61e61eea2cb78bbd096e7b4db2117322ad8099fb ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.oRTdHgy2CM/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) [수집 2건 중 전순서 최소]
u17_rc=1

########## F-5 회귀 ⑤-b live — 선언 owner_repo=octocat/Hello-World ⇒ PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: octocat/Hello-World
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 0edae51 2026-08-19T21:20:21+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b6878fb 2026-08-19T21:20:21+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-oct/.git/info/grafts=no · is_shallow=false · entry HEAD=0edae514392049b79f1a848289014d233d5fb0f1
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-oct /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ea5MkCRd7A/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=0edae514392049b79f1a848289014d233d5fb0f1 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ea5MkCRd7A/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.PrWVD9Opef
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ea5MkCRd7A/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ea5MkCRd7A/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/decl-oct/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:24Z  http=200  x-github-request-id=EFE6:21B9D:CA83E3:E054A7:6A859F87
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:24Z  http=200  x-github-request-id=BDA5:94A79:C70D8D:DCDDD8:6A859F87  (.default_branch=main)
U17-T declared-vs-pin:  owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) (declared owner_repo=octocat/Hello-World target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:24Z  http=200  x-github-request-id=E7AD:346330:C74207:DD0CB1:6A859F88
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:25Z  http=200  x-github-request-id=486E:346330:C742E4:DD0D60:6A859F89
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:25Z  http=200  x-github-request-id=4505:201076:C80B66:DDD9CD:6A859F89
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:26Z  http=200  x-github-request-id=2A3F:C76AD:C899F4:DE65CF:6A859F8A
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[0edae514392049b79f1a848289014d233d5fb0f1 ] P_last(집합·|1|·blob=b4a54ba6b16b9e4a3524da195985e1ce804d6013)=[0edae514392049b79f1a848289014d233d5fb0f1 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Ea5MkCRd7A/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## F-6 회귀 ⑩-a live — 원격이 타 host(gitlab.com) ⇒ PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://gitlab.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * dc1e336 2026-08-19T21:20:27+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 8d8b3cd 2026-08-19T21:20:27+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-gitlab/.git/info/grafts=no · is_shallow=false · entry HEAD=dc1e336c7dfa6b5dc15aecf688ec4e4a13f2fb2f
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-gitlab /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yszjzzSYbP/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=dc1e336c7dfa6b5dc15aecf688ec4e4a13f2fb2f · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yszjzzSYbP/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=gitlab.com/kakao-harris-lee/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.CB8MQ9jGc5
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yszjzzSYbP/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yszjzzSYbP/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-gitlab/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:29Z  http=200  x-github-request-id=D397:33C891:CD8D0F:E35DCF:6A859F8C
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:29Z  http=200  x-github-request-id=7282:21B9D:CA8953:E05AB4:6A859F8D  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:30Z  http=200  x-github-request-id=2585:33C891:CD8E27:E35F06:6A859F8D
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:30Z  http=200  x-github-request-id=1FFB:C76AD:C89D9C:DE69EE:6A859F8E
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:31Z  http=200  x-github-request-id=87D4:201076:C80FF7:DDDF22:6A859F8E
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:31Z  http=200  x-github-request-id=14F6:346330:C7488D:DD13E0:6A859F8F
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[dc1e336c7dfa6b5dc15aecf688ec4e4a13f2fb2f ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[dc1e336c7dfa6b5dc15aecf688ec4e4a13f2fb2f ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yszjzzSYbP/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## F-7 회귀 ⑩-b live — 원격이 타 owner ⇒ PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	git@github.com:octocat/kis_unified_sts.git (fetch)
  | origin	git@github.com:octocat/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * f46b0a9 2026-08-19T21:20:32+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * d3c89ed 2026-08-19T21:20:32+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-oct/.git/info/grafts=no · is_shallow=false · entry HEAD=f46b0a932be8ca6b9b450dac88f42e3223639523
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-oct /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DnkyW3wJZR/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=f46b0a932be8ca6b9b450dac88f42e3223639523 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DnkyW3wJZR/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 2개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/octocat/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7KEhDoRtBz
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DnkyW3wJZR/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DnkyW3wJZR/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/rem-oct/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:34Z  http=200  x-github-request-id=CA3B:11185E:CC1072:E1DFFB:6A859F91
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:34Z  http=200  x-github-request-id=2512:328E21:C8D5E9:DEA250:6A859F92  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:35Z  http=200  x-github-request-id=1563:94A79:C716B7:DCE89A:6A859F93
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:35Z  http=200  x-github-request-id=C701:177308:C9110C:DEE015:6A859F93
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:36Z  http=200  x-github-request-id=4A96:201076:C813EA:DDE3AC:6A859F94
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T12:20:37Z  http=200  x-github-request-id=473A:335F3A:C7D753:DDA7C1:6A859F94
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first(집합·|1|)=[f46b0a932be8ca6b9b450dac88f42e3223639523 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[f46b0a932be8ca6b9b450dac88f42e3223639523 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DnkyW3wJZR/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_TARGET_MISMATCH
reason=계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts) [수집 2건 중 전순서 최소]
u17_rc=1

########## F-8 회귀 ⑨-a — 착수 «후» 아티팩트 편집 ⇒ PREVENTION_ARTIFACT_MUTATED ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED (edited AFTER d)
  * 8c8aa56 2026-08-19T21:20:38+09:00 P_edit: artifact edited after D0-A start (SIMULATED)
  * 7a4686a 2026-08-19T21:20:38+09:00 D0-A: introduce config/tos_completion.yaml
  * 0f9383b 2026-08-19T21:20:37+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 6c8cc8c 2026-08-19T21:20:37+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 1742bcc 2026-08-19T21:20:37+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/mut bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/mutated/.git/info/grafts=no · is_shallow=false · entry HEAD=8c8aa56e9d535c52d27f9aa4f4d676051356cb43
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/mutated /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pxeT312YwH/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=8c8aa56e9d535c52d27f9aa4f4d676051356cb43 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pxeT312YwH/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 5개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/mut capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.dxIjlyzQ4N
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/mut — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pxeT312YwH/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pxeT312YwH/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/mutated/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:20:39Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:20:39Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:20:39Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:20:39Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:20:39Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:20:39Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[6c8cc8cc61f771e1aad73b094dc383439300b28c ] P_last(집합·|1|·blob=48c96a905c1eff6794582391c2dc1c558c983c12)=[8c8aa56e9d535c52d27f9aa4f4d676051356cb43 ] |D|=1 D=[7a4686a406f802ccf9aaa53001a7c36dbd10efff ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 3건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pxeT312YwH/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-fire PREVENTION_ARTIFACT_MUTATED: [E9] ¬LATE ∧ ∃d∈D: x_last=8c8aa56e9d535c52d27f9aa4f4d676051356cb43 ⋠ d — 착수 «후» 아티팩트 변경
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/7a4686a406f802ccf9aaa53001a7c36dbd10efff/pulls  utc=2026-08-19T12:20:40Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/0f9383ba00d908e0d5c5f12f43392ebd49693b5b/check-runs  utc=2026-08-19T12:20:40Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:20:40Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:20:40Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=0f9383ba00d908e0d5c5f12f43392ebd49693b5b  utc=2026-08-19T12:20:41Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@0f9383ba00d908e0d5c5f12f43392ebd49693b5b (encoding=base64 size=441):
  | name: tos-gate
  | on: [pull_request]
  | jobs:
  |   tos-gate:
  |     runs-on: ubuntu-latest
  |     steps:
  |       - name: "tos-gate: run harness"
  |         run: |
  |           set -euo pipefail
  |           bash tools/tos_entry_harness.sh
  |       - name: "tos-gate: verify harness sha256"
  |         run: |
  |           set -euo pipefail
  |           printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = True
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = BLOB_OK
  | RESULT=BLOB_OK
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:20:41Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"0f9383ba00d908e0d5c5f12f43392ebd49693b5b","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show 0f9383ba00d908e0d5c5f12f43392ebd49693b5b:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=7a4686a406f802ccf9aaa53001a7c36dbd10efff head=0f9383ba00d908e0d5c5f12f43392ebd49693b5b merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=[E9] ¬LATE ∧ ∃d∈D: x_last=8c8aa56e9d535c52d27f9aa4f4d676051356cb43 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## G. #2 실측 — 비순환 생산 순서 (계약·개발계획 리터럴 원문 병기) ##########
-- (1) UNCHK-008 레지스터 행 (owner_track 열) — 리터럴 앵커로 찾는다 --
  계약 :6228  owner_track=« `Phase 0` » · closable=« `YES` »
  본문 발췌: [v2.21 — 심판 #2] 이 축의 도입(룰셋 required check·`.github/workflows/tos-gate.yml`·하니스 파일 실체화)은 D0-A 착수 «전» 운영자/인프라 선행 단계이며 U-17 이 live 검증한다 — �
-- (2) 산문 2곳 (v2.21 전파) --
  4985:예방(진입 표면 거부)   **`UNCHK-008` 소관**(`Phase 0` — **[v2.21]** D0-A 착수 전 선행조건·운영자/인프라) — 브랜치 보호·훅은
  5112:          **닫지 못하는 것**: **근면한 세탁**. **예방은 `UNCHK-008`(`Phase 0` — **[v2.21]** D0-A 선행조건)**
-- (3) U-17 하니스 «pre-D0-A 실체화» 리터럴 --
  213:| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`fals
  4404:| **#2 #5/#6 비순환 생산 순서** (medium) | UNCHK-008 `owner_track=Phase 1`·U-17 하니스 «D0-A 산출물» — Phase 0 소비 전 산출·폐쇄 주체 단일 비순환 순서 부재 | **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 선행조건·운영자/인프라·산문 2곳 전파) · **U-17 하니스 «D0-A 산출물»→
  4480:②′ **[v2.21 — 심판 #2 연장]** ②의 예방 통제 불릿에 **하니스 파일 실체화**를 같은 선행조건으로 추가 — **운영자 승인 (D) 개정의 «연장»**(같은 대상·같은 pre-D0-A 주체·시점: UNCHK-008 `owner_track=Phase 0`·U-17 하니스 «pre-D0-A 실체화»와 정합):
  5480:                             (경로 리터럴은 계약이 정한다 · **[v2.21 — 심판 #2] 하니스 «파일»은 «pre-D0-A 실체화»** —
  6228:| UNCHK-008 | **저장소 밖 강제 표면** — CI 필수 잡(required check) · **[v2.13] 진입 표면 거부**(브랜치 보호·pre-receive/pre-commit 훅) | 브랜치 보호 설정이라 저장소 내 파일로 증명 불가. `tos-firewall.yml`도 "NOT configured here"를 자인 | GitHub 브랜치 보호 설정 + 증거 보존 (상위 `TOS-
-- (4) 개발계획 Phase 0 선행 조건 불릿 (하니스 파일 실체화 포함) --
  :270  선행 조건 (D0-A 착수 전):
  :271  
  :272  - **예방 통제 활성**: tos-gate required check(룰셋 — `required_status_checks.checks[].app_id`
  :273    == Actions app id)·`.github/workflows/tos-gate.yml`(하니스 `tools/tos_entry_harness.sh`
  :274    경로·sha256 검증 스텝 포함) **및 그 하니스 파일 `tools/tos_entry_harness.sh` 의
  :275    실체화(계약 §12.3.4-R 블록 결속값 sha 957bf49d…)** 도입 → D0-A 착수 전 `PREVENTION_ACTIVE`(계약 §12.3.4 `U-17`).
  :276  
  :277  종료 조건:
-- (5) 본 저장소 현행 실물 — 아티팩트·워크플로·하니스 파일 --
  tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md 부재
  .github/workflows/tos-gate.yml                                 부재
  tools/tos_entry_harness.sh                                     부재
  config/tos_completion.yaml                                     부재
-- (6) 본 저장소 live U-17 상태 (GET · 실행기 1회) --
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1wWud2eY88
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:22:57Z  http=200  x-github-request-id=666A:21B9D:CB06E3:E0EA74:6A85A020
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:22:58Z  http=200  x-github-request-id=0938:177308:C98DD8:DF6E6E:6A85A021
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
  u17_rc=1

########## G-2 순서 실증(SIMULATED) — «아티팩트 + 하니스 파일 실체화 + 룰셋 캡처» 가 D0-A 산출물 «없이» 성립하면 PREVENTION_ACTIVE 에 도달한다 ##########
  커밋 순서:
    983b7c3 seed
    319e2bf pre-D0-A: materialize tools/tos_entry_harness.sh (operator/infra)
    e15c660 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
    9d67dbe W: add .github/workflows/tos-gate.yml (SIMULATED)
  D0-A 산출물(config/tos_completion.yaml) 존재? NO ← D0-A 미착수 · D = ∅
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 9d67dbe 2026-08-19T21:22:59+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * e15c660 2026-08-19T21:22:59+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 319e2bf 2026-08-19T21:22:59+09:00 pre-D0-A: materialize tools/tos_entry_harness.sh (operator/infra)
  * 983b7c3 2026-08-19T21:22:59+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A/.git/info/grafts=no · is_shallow=false · entry HEAD=9d67dbe540961c1d25e150a402ced8bf440a963f
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=9d67dbe540961c1d25e150a402ced8bf440a963f · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.bGaNK2Qj1r
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx84v221/preD0A/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:23:00Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:23:00Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:23:01Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[e15c660d4dcacb58038a3184c6da4170e6df89d7 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[e15c660d4dcacb58038a3184c6da4170e6df89d7 ] |D|=0 D=[ ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 1건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.Q1dmUNcRTt/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=0) ∧ (α) 연속성 성립(t_land=∅) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam221/pre
u17_rc=0
  ⇒ 정직 경계: 이 픽스처는 «순서»(pre-D0-A 실체화 → D0-A 착수)만 실증한다 — 실환경 룰셋·워크플로 도입은 인프라/운영자 소관이며 이 증거가 대신하지 않는다
```

## 11. 실행기·술어·드라이버·픽스처 생성기 원문

### 11-1. 판정 실행기 `u17-verify-v221.sh` (sha256 `5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727` · 486행)

```bash
#!/usr/bin/env bash
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
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
WFSTRUCT="${U17_WFSTRUCT:-$(dirname "$0")/wfcanon-v221.py}"   # [v2.21 #1] «정본 대조» 술어 (YAML 파서 + 정규화 후 byte 비교)
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
    # ── [v2.21 #1 (1)] 정본 대조 — «토큰 존재»가 아니라 «정본 byte 일치» (열린-세계 → 닫힌-세계)
    WFF="$CAP/$(key "$CQ").wf.yml"; printf '%s\n' "$WF" > "$WFF"
    WFOUT=$(WF_GATE_JOB="$CHECK" WF_HARNESS="$LIT1" WF_SHA="$LIT2" python3 "$WFSTRUCT" blob "$WFF" 2>&1); WFRC=$?
    printf '%s\n' "$WFOUT" | sed 's/^/  | /'
    WFRES=$(printf '%s\n' "$WFOUT" | sed -n 's/^RESULT=//p' | tail -1)
    case "$WFRES" in
      UNVERIFIABLE) fire PREVENTION_UNVERIFIABLE "(b)③ d=$d head=$HSHA 워크플로 blob 정본 대조 불가(YAML 파서 실패)"; continue ;;
      BLOB_OK) : ;;
      *) fire PREVENTION_UNVERIFIED_REVISION "(b)③ d=$d head=$HSHA 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)"; continue ;;
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

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```

### 11-2. 정본 대조 술어 `wfcanon-v221.py` (sha256 `a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d` · 159행)

```python
#!/usr/bin/env python3
"""U-17 (b)③ «정본 대조» 술어 — v2.21 계약 0528a919 :5467-5510 의 문자 구현.

계약 문언(요약 인용):
  (1) blob «정본 대조» — YAML 파서(기존 도구)로 `jobs.<게이트 잡>.steps[]` 를 얻어 게이트 두 스텝의
      `run:` 을 **정규화 후 계약 «정본»과 byte 대조**한다.  정본과 다르면(선행 exit/exec/가드·서브셸·
      heredoc·eval·`|| true`·`set +e`·선행 종결자 등 «전 구문 우회»를 열거 없이) → UNVERIFIED_REVISION.
      정규화(결정적): CRLF→LF · 각 줄 trailing 공백(**ASCII `[ \t]` 만**) 제거 · «빈 줄»과 «full-line
      주석»(첫 비-공백 문자가 `#`) 제거 · 남은 줄을 LF 로 결합.
      스텝 메타(닫힌 키 집합): `shell` 정본값만 · `continue-on-error: true` 부재 · `if` 부재/`success()` ·
      `timeout-minutes` ≠ 0 · run 스텝은 `name`·`run`·(선택 `shell`) «외 키 부재».
  (2) 서버 잡 스텝 대조 — v2.20 과 동일(스텝 이름·conclusion).

운영자 지침(CLAUDE.md Development Discipline: 바퀴 재발명 금지) 이행:
  · YAML 파싱은 **기존 도구 `yq`**(mikefarah) · 대조는 **byte 비교**(표준 문자열 연산)뿐.
  · v2.20 술어의 **자작 셸 토크나이저·명령 위치 판별기는 폐기**(정본 대조가 그 클래스를 열거 없이 닫는다).
출력: `WF-*` 관측 라인 + 마지막 줄 `RESULT=BLOB_OK|UNVERIFIED_REVISION|UNVERIFIABLE` · rc 0/1/2.
"""
import json, os, subprocess, sys

GATE_JOB = os.environ.get("WF_GATE_JOB", "tos-gate")
HARNESS  = os.environ.get("WF_HARNESS", "tools/tos_entry_harness.sh")
SHA      = os.environ.get("WF_SHA", "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d")
STEP_RUN = os.environ.get("WF_STEP_RUN", "tos-gate: run harness")
STEP_VER = os.environ.get("WF_STEP_VER", "tos-gate: verify harness sha256")

# ── 계약 정본 (계약 :5473-5490 코드펜스 원문에서 그대로 옮긴 리터럴)
CANON_A = "set -euo pipefail\nbash %s" % HARNESS
CANON_B = ("set -euo pipefail\n"
           r"printf '%s  " + HARNESS + r"\n' " + SHA + " | shasum -a 256 -c -")
CANON_B = CANON_B.replace("printf '%s  ", "printf '%s  ")   # (표기 고정 — 두 칸 공백)
SHELL_OK = {"bash", "bash -euo pipefail {0}", "bash -eo pipefail {0}"}
ALLOWED_KEYS = {"name", "run", "shell"}


def normalize(run):
    """계약 정규화 규칙 — CRLF→LF · 줄 trailing ASCII [ \\t] 제거 · 빈 줄/full-line 주석 제거 · LF 결합."""
    s = run.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in s.split("\n"):
        line = line.rstrip(" \t")             # [ASCII 핀] NBSP 등 유니코드 공백은 «제거하지 않는다»
        if line.strip(" \t") == "":
            continue
        if line.lstrip(" \t").startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def parse_yaml(path):
    """기존 도구 재사용 — mikefarah yq (진짜 YAML 파서·주석 폐기·folded/literal 스칼라 처리)."""
    r = subprocess.run(["yq", "-o=json", ".", path], capture_output=True, text=True)
    if r.returncode != 0:
        return None, "yq 파싱 실패: " + r.stderr.strip()[:200]
    try:
        return json.loads(r.stdout), ""
    except Exception as e:
        return None, "JSON 변환 실패: %r" % (e,)


def meta_check(st, kind):
    """닫힌 메타 키 집합 (계약 :5504-5507)."""
    why = []
    if st.get("continue-on-error") in (True, "true"):
        why.append("continue-on-error: true")
    if "if" in st and str(st["if"]).strip() not in ("success()", "${{ success() }}"):
        why.append("if: %r" % (st["if"],))
    if "timeout-minutes" in st:
        try:
            if int(st["timeout-minutes"]) == 0:
                why.append("timeout-minutes: 0")
        except Exception:
            why.append("timeout-minutes: %r(비수치)" % (st["timeout-minutes"],))
    if "shell" in st and str(st["shell"]).strip() not in SHELL_OK:
        why.append("shell: %r (정본값 아님)" % (st["shell"],))
    extra = sorted(set(st) - ALLOWED_KEYS - {"continue-on-error", "if", "timeout-minutes"})
    if extra:
        why.append("추가 메타 키 %s (닫힌 집합 위배)" % extra)
    return (not why), "; ".join(why)


def blob_layer(path):
    doc, err = parse_yaml(path)
    print("WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.%s.steps[] 의 run: «뿐»" % GATE_JOB)
    print("WF-C0 정본 A = %r" % CANON_A)
    print("WF-C0 정본 B = %r" % CANON_B)
    if doc is None:
        print("WF-C1 " + err)
        return "UNVERIFIABLE"
    jobs = (doc or {}).get("jobs") or {}
    if GATE_JOB not in jobs:
        print("WF-C1 게이트 잡 «%s» 부재 (jobs=%s)" % (GATE_JOB, list(jobs)))
        return "UNVERIFIED_REVISION"
    steps = (jobs[GATE_JOB] or {}).get("steps") or []
    print("WF-C1 steps[] 이름 = %s" % [s.get("name") for s in steps])
    verdict = "BLOB_OK"
    for want, canon, kind in ((STEP_RUN, CANON_A, "A/run harness"), (STEP_VER, CANON_B, "B/verify sha256")):
        hit = [s for s in steps if s.get("name") == want]
        if not hit:
            print("WF-C2 [%s] 스텝 이름 «%s» 부재 → UNVERIFIED_REVISION" % (kind, want))
            verdict = "UNVERIFIED_REVISION"
            continue
        st = hit[0]
        run = st.get("run")
        if not isinstance(run, str):
            print("WF-C2 [%s] run: 실행문 부재(run 이 문자열 아님) → UNVERIFIED_REVISION" % kind)
            verdict = "UNVERIFIED_REVISION"
            continue
        nrm = normalize(run)
        same = (nrm == canon)
        print("WF-C2 [%s] run 원문     = %r" % (kind, run))
        print("WF-C3 [%s] 정규형       = %r" % (kind, nrm))
        print("WF-C3 [%s] 정본         = %r" % (kind, canon))
        print("WF-C4 [%s] byte 일치    = %s%s" % (kind, same,
              "" if same else "  ← 첫 불일치 오프셋 %d" % next((i for i, (x, y) in enumerate(zip(nrm, canon)) if x != y), min(len(nrm), len(canon)))))
        mok, mwhy = meta_check(st, kind)
        print("WF-C5 [%s] 스텝 키 = %s · 메타 닫힌 집합 = %s%s" % (kind, sorted(st), mok, "" if mok else " (%s)" % mwhy))
        if not (same and mok):
            verdict = "UNVERIFIED_REVISION"
    print("WF-C6 blob 층 판정 = %s" % verdict)
    return verdict


def server_layer(path):
    """actions/runs/{run_id}/jobs 응답에서 게이트 잡·두 스텝 이름·conclusion 대조 (v2.20 과 동일)."""
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

### 11-3. 픽스처 생성기 `mkwf-v221.py` (sha256 `f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5` · 79행)

```python
#!/usr/bin/env python3
"""t84v221 워크플로 픽스처 생성기 — «바이트 정확» YAML 을 파일로 쓴다.

검증자 산출물(`v221-verify/itemD_canon/canon.py` 의 `wf()` 빌더)과 같은 형태를 재사용하되,
이 파일이 «증거 실행기가 실제로 소비한» 픽스처의 유일 소스다.  각 케이스는 (id, 기대, 설명, bytes).
"""
import os, sys

SHA = "957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d"
RUNA = "set -euo pipefail\nbash tools/tos_entry_harness.sh"
RUNB = "set -euo pipefail\n" + r"printf '%s  tools/tos_entry_harness.sh\n' " + SHA + " | shasum -a 256 -c -"
HDR = "name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n"


def wf(run_a=RUNA, run_b=RUNB, meta_a="", meta_b="", scalar_a="|", scalar_b="|"):
    """scalar 는 스텝별로 준다 — folded(`>`)는 «줄 접기»가 의미를 바꾸므로 A 에만 쓴다(B 는 파이프라인 한 줄)."""
    def block(name, meta, run, scalar):
        body = "\n".join("          " + ln if ln else "" for ln in run.split("\n"))
        m = ("\n" + "\n".join("        " + x for x in meta.split("\n"))) if meta else ""
        return f'      - name: "{name}"{m}\n        run: {scalar}\n{body}'
    return HDR + block("tos-gate: run harness", meta_a, run_a, scalar_a) + "\n" + \
           block("tos-gate: verify harness sha256", meta_b, run_b, scalar_b) + "\n"


CASES = [
    ("pos-canonical",      "BLOB_OK",             "양성 — 정본 A/B 정확", wf()),
    ("ctrl-comments",      "BLOB_OK",             "정규화 대조군 — full-line 주석 + 빈 줄 추가",
     wf("# lead comment\nset -euo pipefail\n\nbash tools/tos_entry_harness.sh\n# trailer", RUNB)),
    ("ctrl-trailing-ws",   "BLOB_OK",             "정규화 대조군 — trailing 공백/탭",
     wf("set -euo pipefail   \nbash tools/tos_entry_harness.sh\t", RUNB)),
    ("ctrl-crlf",          "BLOB_OK",             "정규화 대조군 — CRLF 줄끝",
     wf(RUNA.replace("\n", "\r\n"), RUNB)),
    ("ctrl-folded",        "BLOB_OK",             "정규화 대조군 — 스텝 A 를 folded `>` 로 «의미 동일» 표기(빈 줄=줄바꿈 접기)",
     wf("set -euo pipefail\n\nbash tools/tos_entry_harness.sh", RUNB, scalar_a=">")),
    ("13a-echo",           "UNVERIFIED_REVISION", "⑬a — 하니스가 echo 인자",
     wf('set -euo pipefail\necho "bash tools/tos_entry_harness.sh"', RUNB)),
    ("13b-trailcomment",   "UNVERIFIED_REVISION", "⑬b — trailing 주석(정규화가 제거하지 않는다)",
     wf("set -euo pipefail\nbash tools/tos_entry_harness.sh  # run it", RUNB)),
    ("13c-ortrue",         "UNVERIFIED_REVISION", "⑬c — `|| true` 무효화 (v2.20 «미검출» → v2.21 검출)",
     wf(RUNA, RUNB + " || true")),
    ("13d-unreachable",    "UNVERIFIED_REVISION", "⑬d — 도달 불가 호출 `false && …`",
     wf("set -euo pipefail\nfalse && bash tools/tos_entry_harness.sh || true", RUNB)),
    ("13e-continue",       "UNVERIFIED_REVISION", "⑬e — continue-on-error: true", wf(meta_b="continue-on-error: true")),
    ("13e-if-always",      "UNVERIFIED_REVISION", "⑬e — if: always()", wf(meta_b="if: always()")),
    ("13e-extra-key",      "UNVERIFIED_REVISION", "⑬e — 추가 메타 키(env:) = 닫힌 집합 위배",
     wf(meta_b="env:\n  FOO: bar")),
    ("13f-set-plus-e",     "UNVERIFIED_REVISION", "⑬f — set +e",
     wf(RUNA, "set -euo pipefail\nset +e\n" + RUNB.split("\n")[1])),
    ("13f-trap",           "UNVERIFIED_REVISION", "⑬f — trap … ERR",
     wf(RUNA, "set -euo pipefail\ntrap 'exit 0' ERR\n" + RUNB.split("\n")[1])),
    ("13g-exit0",          "UNVERIFIED_REVISION", "⑬g — 선행 종결자 `exit 0`",
     wf("set -euo pipefail\nexit 0\nbash tools/tos_entry_harness.sh", RUNB)),
    ("13g-exec-true",      "UNVERIFIED_REVISION", "⑬g — 선행 종결자 `exec true`",
     wf("set -euo pipefail\nexec true\nbash tools/tos_entry_harness.sh", RUNB)),
    ("13g-guarded-exit",   "UNVERIFIED_REVISION", "⑬g — 선행 종결자 `[ -n \"${SKIP:-}\" ] && exit 0`",
     wf('set -euo pipefail\n[ -n "${SKIP:-}" ] && exit 0\nbash tools/tos_entry_harness.sh', RUNB)),
    ("nbsp-trailing",      "UNVERIFIED_REVISION", "NBSP trailing (ASCII 핀 — 유니코드 공백은 제거하지 않는다)",
     wf("set -euo pipefail \nbash tools/tos_entry_harness.sh", RUNB)),
    ("inline-semicolon",   "UNVERIFIED_REVISION", "inline `;` 한 줄 (허용 정본 집합 1)",
     wf("set -euo pipefail; bash tools/tos_entry_harness.sh", RUNB)),
    ("env-bash",           "UNVERIFIED_REVISION", "`env bash …` (정본 아님)",
     wf("set -euo pipefail\nenv bash tools/tos_entry_harness.sh", RUNB)),
    ("shell-no-set",       "UNVERIFIED_REVISION", "shell: bash -euo pipefail {0} + `set` 줄 없음",
     wf("bash tools/tos_entry_harness.sh", RUNB.split("\n")[1],
        meta_a="shell: bash -euo pipefail {0}", meta_b="shell: bash -euo pipefail {0}")),
]

BOM_CASE = ("ctrl-bom", "BLOB_OK", "정규화 대조군 — UTF-8 BOM 선두", "﻿" + wf())

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    idx = []
    for cid, exp, desc, text in CASES + [BOM_CASE]:
        with open(os.path.join(out, cid + ".yml"), "wb") as f:
            f.write(text.encode("utf-8"))
        idx.append("%s|%s|%s" % (cid, exp, desc))
    open(os.path.join(out, "INDEX.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
    print("fixtures=%d → %s" % (len(idx), out))
```

### 11-4. 드라이버 `t84v221.sh` (sha256 `962cc027f88a9ff2adad807c08136132de8168e651c0a3006661fa6022bb9a72` · 268행)

```bash
#!/usr/bin/env bash
# t84v221.sh — v2.21(계약 0528a919) T-84 드라이버:
#   A 정본 리터럴 결속 · B blob «정본 대조» 배터리 22종(양성·정규화 대조군·⑬a~⑬g·NBSP·inline·env bash·shell-no-set)
#   C 서버 steps[] mock(⑭ 4종) · D e2e(양성 ACTIVE · ⑬g/⑬c UNVERIFIED_REVISION + v2.20 실행기 대조군)
#   E 정본 B 런타임 실증 · F 회귀(⑤⑩ live·⑨·⑪(a)(b)·⑫) · G #2 실측(리터럴 병기·live 1회·순서 SIMULATED)
#   t84v220.sh 헬퍼 블록 원문 재사용 + 실행기/술어 교체.  GET-only · 서버 쓰기 0 · 픽스처는 scratchpad 독립 repo.
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence
SP20=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v220-evidence
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

EX="$SP/u17-verify-v221.sh"                       # 판정 실행기 (정본 대조)
WFS="$SP/wfcanon-v221.py"                         # (b)③ 정본 대조 술어
EX220="$SP20/u17-verify-v220.sh"                  # 직전 판 실행기 — 구조 파싱 (⑬ 판별력 대조)
FX="$SP/fx84v221"; SEAM="$SP/seam221"
rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't84v221_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$WFS" "$EX220" "$SP/mkwf-v221.py"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf -- '-- 판정 실행기 vs 직전 판(v2.20) diff 행수 = %s (델타: 술어 파일 교체 1건) --\n' "$(diff "$EX220" "$EX" | grep -c '^[<>]')"
printf 'git=%s · gh=%s · yq=%s · python3=%s\n' "$(git --version)" "$(gh --version | head -1)" "$(yq --version)" "$(python3 -V)"
inj_wf(){ printf '%s' "$2" > "$1/wf.txt"; inject "$1" "repos/$OR/contents/$WF?ref=$3" 200 "$(contents_json "$1/wf.txt" "$(git hash-object "$1/wf.txt")" "$WF")"; }

########################################################################
sec "A. 정본 리터럴 결속 — 계약 코드펜스 원문 == 술어 CANON_A/B (리터럴 앵커로 추출·행 번호 하드코딩 금지)"
python3 - "$SP" <<'PYEOF'
import sys, pathlib, importlib.util
SP = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("w", SP / "wfcanon-v221.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
C = pathlib.Path("/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md").read_text(encoding="utf-8").split("\n")
def fence(anchor):
    i = next(k for k, l in enumerate(C) if anchor in l)
    f = [k for k in range(i, i + 14) if C[k].strip() == "```"]
    return "\n".join(C[f[0]+1:f[1]]), f[0]+2, f[1]
A, a1, a2 = fence("정본 A** 와 일치")
B, b1, b2 = fence("정본 B** 와 일치")
print(f"  계약 :{a1}-{a2} 정본 A = {A!r}")
print(f"  술어 CANON_A          = {m.CANON_A!r}   → byte 동일? {A == m.CANON_A}")
print(f"  계약 :{b1}-{b2} 정본 B = {B!r}")
print(f"  술어 CANON_B          = {m.CANON_B!r}   → byte 동일? {B == m.CANON_B}")
print(f"  닫힌 메타 키 집합: 허용 키 {sorted(m.ALLOWED_KEYS)} · shell 정본값 {sorted(m.SHELL_OK)}")
PYEOF

########################################################################
sec "B. blob «정본 대조» 배터리 — 픽스처 22종 (실행기 밖 단위 관측 · 기대는 픽스처 생성기가 «미리» 적은 값)"
python3 "$SP/mkwf-v221.py" "$FX/wf" | sed 's/^/  /'
printf '  %-18s %-22s %-22s %s\n' "id" "기대(계약 T-84 ⑬)" "실측" "설명"
FAIL=0
while IFS='|' read -r cid exp desc; do
  got=$(python3 "$WFS" blob "$FX/wf/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  mark=OK; [ "$got" = "$exp" ] || { mark="MISMATCH"; FAIL=$((FAIL+1)); }
  printf '  %-18s %-22s %-22s %s  [%s]\n' "$cid" "$exp" "$got" "$desc" "$mark"
done < "$FX/wf/INDEX.txt"
echo "  ⇒ 기대와 다른 케이스 = $FAIL 건"
echo
echo "-- 대표 4종 파싱·정규화 원문 (양성 · 정규화 대조군 · ⑬g · NBSP) --"
for c in pos-canonical ctrl-comments 13g-exit0 nbsp-trailing; do
  echo "== $c =="; sed 's/^/  | /' "$FX/wf/$c.yml"; python3 "$WFS" blob "$FX/wf/$c.yml" 2>&1 | sed 's/^/  /'
done

########################################################################
sec "C. 서버 잡 steps[] mock — ⑭ (계약 리터럴 스텝 이름 × conclusion)"
JD="$FX/jobs"; mkdir -p "$JD"
printf '  %-11s %-46s %s\n' "variant" "기대" "실측"
for v in ok noverify verifyfail norun jobfail; do
  jobs_json "$v" deadbeef > "$JD/$v.json"
  case "$v" in ok) EXP="SERVER_OK" ;; *) EXP="UNVERIFIED_REVISION (⑭)" ;; esac
  GOT=$(python3 "$WFS" server "$JD/$v.json" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '  %-11s %-46s %s\n' "$v" "$EXP" "$GOT"
done

########################################################################
sec "D. e2e — 픽스처 저장소(P → W → d) · seam 의 blob 만 바꾼다"
RB="$FX/blob"; mk "$RB"; art "$RB" "$OR" main >/dev/null; WHB=$(wf "$RB" ok); DB=$(d0a "$RB")
echo "  W(PR head)=$WHB  d=$DB"
e2e(){ # e2e <case-id> <seam-name> [executor]
  local S1="$SEAM/$2"; seam_ruleset "$S1" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
  rev_seam "$S1" "$DB" "$WHB" 777001 "$TLAND" ok ok
  inj_wf "$S1" "$(cat "$FX/wf/$1.yml")" "$WHB"
  run "$RB" "file:$S1" "${3:-$EX}"; }

sec "D-1 양성 — 정본 A/B 정확 ⇒ PREVENTION_ACTIVE + rc 0"
e2e pos-canonical pos

sec "D-2 ⑬g 선행 종결자 `exit 0` ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0"
e2e 13g-exit0 g-exit0

sec "D-3 ⑬g 판별력 대조 — 같은 seam 을 «구조 파싱» v2.20 실행기로 → ACTIVE 면 그것이 v2.21 이 닫은 자리(심판 «회피» 지적의 실증)"
e2e 13g-exit0 g-exit0b "$EX220"

sec "D-4 ⑬c `|| true` ⇒ UNVERIFIED_REVISION (v2.20 «미검출» 기대가 뒤집힌 자리)"
e2e 13c-ortrue c-ortrue

sec "D-5 ⑬c 판별력 대조 — v2.20 실행기 (미검출 = ACTIVE 였음을 실증)"
e2e 13c-ortrue c-ortrueb "$EX220"

sec "D-6 정규화 대조군 e2e — 주석·빈 줄만 다른 blob ⇒ 여전히 PREVENTION_ACTIVE"
e2e ctrl-comments ctrl

sec "D-7 ⑭ 서버 스텝 부재 (blob 은 정본 일치) ⇒ UNVERIFIED_REVISION"
S9="$SEAM/s14"; seam_ruleset "$S9" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S9" "$DB" "$WHB" 777001 "$TLAND" ok noverify
inj_wf "$S9" "$(cat "$FX/wf/pos-canonical.yml")" "$WHB"; run "$RB" "file:$S9"

########################################################################
sec "E. 정본 B 런타임 실증 — 계약이 «구조로 보장»한다고 적은 실패 전파를 실제로 돌린다"
RT="$FX/runtime"; mkdir -p "$RT/tools"
printf '#!/usr/bin/env bash\necho harness\n' > "$RT/tools/tos_entry_harness.sh"
REALSHA=$(shasum -a 256 "$RT/tools/tos_entry_harness.sh" | cut -d' ' -f1)
echo "  픽스처 하니스 파일 sha256 = $REALSHA  (계약 결속값 $LIT2 와는 다르다 — 여기서는 «정본 B 의 형식»이 실패를 전파하는지만 본다)"
echo "  \$ printf '%s  tools/tos_entry_harness.sh\\n' <sha> | shasum -a 256 -c -    # 두 칸 공백 포맷"
( cd "$RT" && set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\n' "$REALSHA" | shasum -a 256 -c - ) > "$FX/e-ok.out" 2>&1; ERC=$?; sed 's/^/  | /' "$FX/e-ok.out"; echo "  정상 rc=$ERC"
( cd "$RT" && set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\n' "$LIT2" | shasum -a 256 -c - ) > "$FX/e-bad.out" 2>&1; ERC2=$?; sed 's/^/  | /' "$FX/e-bad.out"; echo "  변조(기대 sha 불일치) rc=$ERC2"
echo "  ⇒ 정본 B 는 sha 불일치에서 shasum -c 가 비-0 → set -euo pipefail 로 스텝 실패(계약 :5491 서술과 일치)"

########################################################################
sec "F-1 회귀 ⑪-(a) SIMULATED — 연속성 정상 ⇒ PREVENTION_ACTIVE"
RC="$FX/cont"; mk "$RC"; art "$RC" "$OR" main >/dev/null; WC=$(wf "$RC" ok); DC=$(d0a "$RC")
SA="$SEAM/11a"; seam_ruleset "$SA" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$SA" "$DC" "$WC" 777001 "$TLAND" ok ok
inj_wf "$SA" "$(cat "$FX/wf/pos-canonical.yml")" "$WC"; run "$RC" "file:$SA"

sec "F-2 회귀 ⑪-(b) SIMULATED — 룰셋 updated_at > t_land ⇒ PREVENTION_CONTINUITY_UNVERIFIABLE"
SB="$SEAM/11b"; seam_ruleset "$SB" 42 2026-08-01T00:00:00Z 2026-08-11T09:00:00Z; rev_seam "$SB" "$DC" "$WC" 777001 "$TLAND" ok ok
inj_wf "$SB" "$(cat "$FX/wf/pos-canonical.yml")" "$WC"; run "$RC" "file:$SB"

sec "F-3 회귀 ⑫ live — GH_HOST override 하 상태 불변"
RH="$FX/host"; mk "$RH"; art "$RH" "$OR" main >/dev/null
run "$RH" gh "$EX"; run "$RH" gh "$EX" "GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy "

sec "F-4 회귀 ⑤-a live — 선언 target=비-default 브랜치 ⇒ PREVENTION_TARGET_MISMATCH"
R5="$FX/decl-wb"; mk "$R5"; art "$R5" "$OR" "$WB" >/dev/null; run "$R5" gh

sec "F-5 회귀 ⑤-b live — 선언 owner_repo=octocat/Hello-World ⇒ PREVENTION_TARGET_MISMATCH"
R6="$FX/decl-oct"; mk "$R6"; art "$R6" "octocat/Hello-World" main >/dev/null; run "$R6" gh

sec "F-6 회귀 ⑩-a live — 원격이 타 host(gitlab.com) ⇒ PREVENTION_TARGET_MISMATCH"
R7="$FX/rem-gitlab"; mk "$R7" https://gitlab.com/kakao-harris-lee/kis_unified_sts.git; art "$R7" "$OR" main >/dev/null; run "$R7" gh

sec "F-7 회귀 ⑩-b live — 원격이 타 owner ⇒ PREVENTION_TARGET_MISMATCH"
R8="$FX/rem-oct"; mk "$R8" git@github.com:octocat/kis_unified_sts.git; art "$R8" "$OR" main >/dev/null; run "$R8" gh

sec "F-8 회귀 ⑨-a — 착수 «후» 아티팩트 편집 ⇒ PREVENTION_ARTIFACT_MUTATED"
R9="$FX/mutated"; mk "$R9"; art "$R9" "$OR" main >/dev/null; W9=$(wf "$R9" ok); D9=$(d0a "$R9")
printf 'owner_repo: %s\ntarget_branch: main\ntos_gate_check: tos-gate\noperator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED (edited AFTER d)\n' "$OR" > "$R9/$PC"
git -C "$R9" add -A; git -C "$R9" commit -q -m "P_edit: artifact edited after D0-A start (SIMULATED)"
S8="$SEAM/mut"; seam_ruleset "$S8" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S8" "$D9" "$W9" 777001 "$TLAND" ok ok
inj_wf "$S8" "$(cat "$FX/wf/pos-canonical.yml")" "$W9"; run "$R9" "file:$S8"

########################################################################
sec "G. #2 실측 — 비순환 생산 순서 (계약·개발계획 리터럴 원문 병기)"
CT=/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
DP=/Users/harris/Development/private/kis_unified_sts/docs/plans/2026-08-11-tos-completion-development-plan.md
echo "-- (1) UNCHK-008 레지스터 행 (owner_track 열) — 리터럴 앵커로 찾는다 --"
awk -F'|' '/^\| UNCHK-008 \|/{printf "  계약 :%d  owner_track=«%s» · closable=«%s»\n", NR, $6, $8}' "$CT"
awk '/^\| UNCHK-008 \|/{print "  본문 발췌: " substr($0, index($0,"[v2.21"), 220)}' "$CT"
echo "-- (2) 산문 2곳 (v2.21 전파) --"
grep -n '`UNCHK-008` 소관' "$CT" | cut -c1-200 | sed 's/^/  /'
grep -n '예방은 `UNCHK-008`(`Phase 0`' "$CT" | cut -c1-200 | sed 's/^/  /'
echo "-- (3) U-17 하니스 «pre-D0-A 실체화» 리터럴 --"
grep -n 'pre-D0-A 실체화' "$CT" | cut -c1-230 | sed 's/^/  /'
echo "-- (4) 개발계획 Phase 0 선행 조건 불릿 (하니스 파일 실체화 포함) --"
awk '/^선행 조건 \(D0-A 착수 전\):/{f=NR} f && NR>=f && NR<=f+7 {printf "  :%d  %s\n", NR, $0}' "$DP"
echo "-- (5) 본 저장소 현행 실물 — 아티팩트·워크플로·하니스 파일 --"
for p in tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md .github/workflows/tos-gate.yml tools/tos_entry_harness.sh config/tos_completion.yaml; do
  printf '  %-62s %s\n' "$p" "$( [ -e "$REPO/$p" ] && echo "실재(sha256 $(shasum -a 256 "$REPO/$p" | cut -c1-16)…)" || echo "부재" )"
done
echo "-- (6) 본 저장소 live U-17 상태 (GET · 실행기 1회) --"
U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO" 2>&1 | grep -aE '^U17-0 |^U17-A1 |^U17-A3 |^prevention_control_state=|^reason='; echo "  u17_rc=${PIPESTATUS[0]}"

sec "G-2 순서 실증(SIMULATED) — «아티팩트 + 하니스 파일 실체화 + 룰셋 캡처» 가 D0-A 산출물 «없이» 성립하면 PREVENTION_ACTIVE 에 도달한다"
RP="$FX/preD0A"; mk "$RP"
mkdir -p "$RP/tools"; printf '#!/usr/bin/env bash\n# SIMULATED harness materialization (pre-D0-A)\necho ENTRY_OK\n' > "$RP/tools/tos_entry_harness.sh"
git -C "$RP" add -A; git -C "$RP" commit -q -m "pre-D0-A: materialize tools/tos_entry_harness.sh (operator/infra)"
art "$RP" "$OR" main >/dev/null; WP=$(wf "$RP" ok)
echo "  커밋 순서:"; git -C "$RP" log --oneline --reverse | sed 's/^/    /'
echo "  D0-A 산출물(config/tos_completion.yaml) 존재? $( [ -e "$RP/config/tos_completion.yaml" ] && echo YES || echo 'NO ← D0-A 미착수' ) · D = ∅"
SP2="$SEAM/pre"; seam_ruleset "$SP2" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
inj_wf "$SP2" "$(cat "$FX/wf/pos-canonical.yml")" "$WP"; run "$RP" "file:$SP2"
echo "  ⇒ 정직 경계: 이 픽스처는 «순서»(pre-D0-A 실체화 → D0-A 착수)만 실증한다 — 실환경 룰셋·워크플로 도입은 인프라/운영자 소관이며 이 증거가 대신하지 않는다"
```

## 12. 관측 보고 · 결함 후보 (등급 · file:line)

### P-1 **[관측 — 닫힌 자리 실증]** v2.20 «구조 파싱»은 ⑬g·⑬c 를 통과시킨다

같은 seam 을 v2.20 실행기로 돌리면 `exit 0; bash tools/…`(⑬g)와 `… || true`(⑬c) 둘 다 **`PREVENTION_ACTIVE`·rc 0**(§6 D-3·D-5). v2.21 정본 대조는 둘 다 `UNVERIFIED_REVISION`. 심판이 «회피»로 판정한 그 자리가 실행으로 닫혔음을 실측으로 고정한다. **등급: 관측(처분 확인).**

### P-2 **[문언 — 경미]** 정규화 대조군의 «folded `>`»는 스텝 B 에 적용하면 «의미 동일»이 아니다

계약 :5501 은 «주석·공백만 다른 blob 은 일치»라고 적고 스칼라 표기(`|` vs `>`)는 언급하지 않는다. 실측: 스텝 A(2줄)는 folded + 빈 줄이면 정본과 일치하지만, **스텝 B 는 파이프라인이 한 줄이라 folded 로 쓰면 두 줄이 «한 줄로 접혀» 정본 불일치**가 된다(이 증거의 초기 픽스처가 그렇게 만들어져 red 였고, 스텝 A 만 folded 로 고쳤다). 즉 «표기 자유도»는 스텝별로 다르다 — **작성자가 folded 로 쓰면 정직한 워크플로도 red** 가 될 수 있다. 계약이 «정본은 literal block(`|`) 표기를 전제한다»를 한 줄 명시하면 이 함정이 사라진다. **등급: 문언(과잉 차단 방향·fail-closed).** file:line = `docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:5499-5501`

### P-3 **[관측]** BOM·CRLF·trailing 공백·주석·빈 줄은 정규화가 흡수한다

`ctrl-bom`·`ctrl-crlf`·`ctrl-trailing-ws`·`ctrl-comments` 전부 `BLOB_OK`(§4). 반면 **NBSP trailing 은 red** — 계약이 «ASCII `[ \t]` 만» 으로 핀한 그대로다(:5499). **등급: 관측(결정성 확인).**

### P-4 **[관측 — 자인 경계 유지]** 정본 일치는 «런타임 실제 실행»이 아니다

계약 :5511-5518 이 적은 잔여(선행 스텝의 `$GITHUB_PATH`/`$GITHUB_ENV` 조작·composite action·스텝 «이름» 위조·GitHub 내부)는 이 증거도 닫지 않는다. §7 은 «정본 B 형식이 실패를 전파한다»만 실증하며, 그 스텝이 실제로 그 바이트를 실행했는지는 서버 «이름·conclusion» 층 위의 주장이 아니다. **등급: 관측(자인 경계).**

### P-5 **[관측]** #2 는 «순서 가능성»까지만 실증된다

본 저장소 현행은 아티팩트·워크플로·하니스 파일·config **전부 부재**이고 live U-17 = `PREVENTION_ABSENT`(§9). 비순환 순서의 «실환경 성립»은 인프라/운영자 작업이며, 이 증거는 SIMULATED 픽스처로 **D0-A 산출물 없이 `PREVENTION_ACTIVE` 도달이 가능함**(순서 무모순)만 보인다. **등급: 관측(정직 경계 명시).**

### P-6 **[fail-open/차단 등급 신규 결함 후보 0]**

계약 문언을 그대로 구현했을 때 green 을 내는 새 자리는 이 회차에서 발견되지 않았다. 22 픽스처 전건이 계약 기대와 일치했고(§4·기대 불일치 0건), ⑬a~⑬g·NBSP·inline·`env bash`·shell-no-set 전부 `UNVERIFIED_REVISION` 이다. 유일한 문언 지적은 P-2(과잉 차단 방향).
