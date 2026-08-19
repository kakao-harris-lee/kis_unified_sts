# U17-PREVENTION-CHECK-V219 — v2.19 T-84 ⑪(연속성 SIMULATED)·⑫(GH_HOST override live) + 회귀(③·⑤·⑨·⑩) 실행 기록 (u17-verify-v219 · C6 host 결속 · U-17-c 10값/전순서 10단 · GET-only)

> **비규범 부속** — 계약 v2.19(`d5a8302a`)도 U-17 증거 아티팩트의 **경로·파일명을 규정하지 않는다**(선행 판과 동일). 이 파일은 v2.18 재심 verdict 스탬프
> `docs/reviews/phase0-completion-contract/20260819-074621/` 의 **sibling** 으로 두며, v2.16~v2.18 sibling(`…/20260819-002145/U17-PREVENTION-CHECK*.md`)은
> U-15-e **(4d) 불변 규율을 준용**해 편집하지 않고 새 파일을 둔다.
> **S-24 결속: 이 증거는 «최종 동결 `d5a8302a`» 에 결속된다** — 실행 시점 HEAD == `d5a8302a` · 계약 워킹트리 blob `a1d52da7` == `git show d5a8302a:<계약>` blob
> (`git diff --quiet d5a8302a -- <계약>` rc=0 · 워킹트리 sha256 `8eba31fa573c34c8f71bae7a3616cc90765e76f25626c48520281c6f5b114f85`) ·
> `d5a8302a..HEAD` 에 계약 문서 커밋 **0**(에라타 없음) · 하니스 §12.3.4-R 블록 `sed -n '4589,4689p'` sha256
> **`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`** — 동결 blob·워킹트리 **byte-동일**(§6 원문).
> **판정 소비자는 이 파일의 응답을 신뢰하지 않고 스스로 live 조회한다**(§12.3.4 «진실 원천» — 이 파일은 **대조용**이다).
> **서버 쓰기·설정 변경 0** — 전 조회가 `gh api -i --hostname github.com <GET path>` 이고 `gh auth status` 는 읽기 전용이다(§6 사후 재조회로 무변경 확인).
> 픽스처는 scratchpad 하위 **독립 git 저장소**(`fx84z/*` — 본 저장소 무접촉·worktree 미사용 · 원격 URL 은 로컬 config 문자열일 뿐 push/fetch 0).

- **생성 시각**: 2026-08-19T01:15:17Z (UTC) · 실행 `t84v219_utc=2026-08-19T01:03:19Z` + 각 캡처 `utc=` · **생성 주체**: 오케스트레이터 지시 하의 실행·조립 에이전트(저작자·심판 아님)
- **실행기 결속**:
  - sha256(`u17-verify-v219.sh`) = **`52dd03193f4e90ac1b369107ee7bd7301cca07b8ed8478d0a271ea48cd82d879`** (원문 §1 · v2.18e `6b196756…` 대비 델타 = **C6 host 결속 + 연속성 소비자 + 전순서 10단**만, `diff` §1-2)
  - sha256(`u17-verify-v219-CTRL-nohost.sh`) = **`c24bf96f0df70fd12724284e8667effd71181e2e71f27be06863586c4c4c0b7a`** (**T-84 ⑫ 대조군** — v2.19 에서 «`--hostname` 명시»·«`GH_HOST` 재핀»·«auth 전제의 `--hostname`» **만** 제거 = v2.18 거동. `diff` 4행, §2. **판정용 아님**)
  - sha256(`t84v219.sh`) = **`75bef9a3d9a652e9f4761324c83bcc14a7d36a41c4b103df5fcaf7c8ae5a15a2`** (드라이버 원문 §3)
  - sha256(`u17-verify-v218e.sh`) = **`6b196756890f580058c38c4b8e1f44e39c95c1b4137a33377af2602ad414a15c`** (직전 판 실행기 — `U17-PREVENTION-CHECK-V218-ADDENDUM.md` §2 원문에서 그대로 추출·재계산 일치. **⑪ 판별력 대조용**)
- **계약 리터럴(실행기 상수)**: 핀 `github.com/kakao-harris-lee/kis_unified_sts` · **핀 host `github.com`(핀에서 «파생» — 아티팩트 파라미터 아님)** · 워크플로 경로 `.github/workflows/tos-gate.yml` · 하니스 경로 `tools/tos_entry_harness.sh` · 하니스 sha256 `957bf49d…`
- **서버 파생 실측**(§4 A00/A0 캡처 원문): `apps/github-actions` `.id` = **15368** · `repos/{pin}` `.default_branch` = **`main`** · 본 저장소 `git remote -v` = `origin https://github.com/kakao-harris-lee/kis_unified_sts.git`(핀 일치) · 응답 헤더 `X-GitHub-Request-Id` 는 매 캡처 라인에 병기(C6 «가능 시 보조 대조»)
- **U-15 3단 가드**(§12.3.4 (d))는 v2.19 가 U-15 하니스를 바꾸지 않아 재실행하지 않았다 — sibling `…/20260819-002145/U15-ENTRY-CHECK-V216.md` 유효(하니스 블록 sha256 byte-동일을 §6 이 재확인).

## 0. 결과 요약 — 실행기 stdout·rc 원문 그대로 (해석 아님)

실행기는 전 단계를 «수집»한 뒤 **전순서 최소**를 방출한다(`U17-fire` 라인 = 수집 원문 · `[수집 N건 중 전순서 최소]` 사유 병기). **exit 0 = `PREVENTION_ACTIVE` 만.**

| 변이 | 구성 | 방출값 (`prevention_control_state=`) | rc | 기대 (§8 T-84 12종 · U-17-c 10단) | 대조 |
| --- | --- | --- | --- | --- | --- |
| **A 원시 프로브** | `GH_HOST=example.invalid` + `--hostname github.com` / `--hostname` 없음 | 요청 host = **`api.github.com`** / **`example.invalid`**(`/api/v3/…`, `dial tcp … no such host`) | — | C6 근거(심판 실측 프로브) | **일치 — 심판 프로브 재현** |
| **⑫-1 live** 기준선 | 원격=핀 · 선언=핀@main · D=∅ · override 없음 | **`PREVENTION_INSUFFICIENT`** — `classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]` | 1 | ⑫ 기준선 | **일치 (인증 실측)** |
| **⑫-2 live** override | 같은 픽스처를 `GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy` 로 실행 | **`PREVENTION_INSUFFICIENT`** — **⑫-1 과 문자열까지 동일** · `U17-H … 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com … rc=0` | 1 | ⑫ «상태값이 override 유무와 «불변»» | **일치** |
| **⑫-3 live** host 캡처 | 같은 실행을 `GH_DEBUG=api` 로 · 캡처 디렉터리 `*.err` 전수 grep | `6 * Request to https://api.github.com/…` · `6 > Host: api.github.com` | — | ⑫ «조회가 여전히 github.com 으로» | **일치 — 전 요청 6/6 핀 host** |
| **⑫-4 대조군** | `--hostname`·재핀 제거 변형 + 같은 override | **`PREVENTION_UNVERIFIABLE`** — `[C6] gh auth status 실패(rc=1) — 핀 host 인증 부재 (타 host 폴백 없음)` [수집 3건 중 전순서 최소] | 1 | ⑫ «핀 host 도달·인증 불가면 UNVERIFIABLE(fail-closed)» | **일치** |
| **⑫-5 대조군** host 캡처 | 같은 대조군 + `GH_DEBUG=api` | `2 * Request to https://example.invalid/…` · `2 > Host: example.invalid` | — | ⑫ «타 host 로 간다» | **일치 — 위조 표면 실증(도달 시 응답이 판정 입력)** |
| **⑫-6 대조군** override 없음 | 같은 대조군 · override 없음 | **`PREVENTION_INSUFFICIENT`** (⑫-1 과 동일) | 1 | 델타가 **override 민감도**임을 고정 | **일치** |
| **⑪-(a) SIMULATED** 정상 | 적용 룰셋 42 `created_at 2026-08-01`·`updated_at 2026-08-05` ≤ `t_land 2026-08-10` | **`PREVENTION_ACTIVE`** | **0** | ⑪ «≤ t_land 캡처 → 그 축 통과» | **일치 (모의)** |
| **⑪-(b) SIMULATED** off→merge→on | 같은 룰셋 `updated_at 2026-08-11T09:00Z` > `t_land` | **`PREVENTION_CONTINUITY_UNVERIFIABLE`** — `ruleset 42 updated_at … > t_land … benign/malign 구별 불가` | 1 | ⑪ 본체 | **일치** |
| **⑪-(b′) 판별력 대조** | 같은 (b) seam 을 **직전 판 실행기**(`6b196756…`)로 | **`PREVENTION_ACTIVE`** / 0 | 0 | «두 조회가 둘 다 ACTIVE 면 통과»로 접는 구현은 통과시킨다 | **일치 — v2.19 가 닫은 자리의 실증** |
| **⑪-(c) SIMULATED** 삭제-재생성 | 새 id **77** · `created_at 2026-08-12` > `t_land` | **`PREVENTION_CONTINUITY_UNVERIFIABLE`** — `created_at … > t_land … 그 착지는 비보호` | 1 | ⑪ «삭제-재생성은 새 id·created_at 로 검출» | **일치** |
| **⑪-(d) SIMULATED** classic-only | protection 이 (a) 술어 충족 · `rules/branches/main = []`(적용 룰셋 0) | **`PREVENTION_CONTINUITY_UNVERIFIABLE`** — `적용 룰셋 0 = classic … created_at·updated_at 부재` | 1 | ⑪ «classic-only 도 판정 불가» | **일치** |
| **⑪-(d′) 판별력 대조** | 같은 (d) seam 을 직전 판 실행기로 | **`PREVENTION_ACTIVE`** / 0 | 0 | v2.18 은 연속성을 묻지 않는다 | **일치** |
| **⑪-(e) SIMULATED** direct-push | 착지 PR 없음(`pulls=[]`) + 룰셋 `updated_at > t_land` | **`PREVENTION_UNVERIFIED_REVISION`** (수집: `UNVERIFIED_REVISION`(8)·`CONTINUITY_UNVERIFIABLE`(9) → 8) | 1 | 전순서 8 < 9 — (b) 선발화 | **일치** |
| **⑪-(f) SIMULATED** committer-date 무시 | (a) 와 같은 seam · **픽스처 전 커밋 author/committer date = 2026-12-31**(t_land 보다 늦다) | **`PREVENTION_ACTIVE`** / 0 | 0 | ⑪ «서버 시간만 소비 — 커밋 시각 불신» | **일치 — 상태값 불변** |
| **회귀 ③** | ⑪-(a) 구성(룰셋 경로) = (b) 양성 SIMULATED seam | **`PREVENTION_ACTIVE`** | 0 | ③ ACTIVE SIMULATED seam | **일치 (모의)** |
| **회귀 ③-classic** | **v2.18 의 ③-b 양성 구성**(classic protection 만)을 v2.19 실행기로 | **`PREVENTION_CONTINUITY_UNVERIFIABLE`** | 1 | — | **v2.18 대비 극성 전환 — §5 결함 후보 D-1 로 보고** |
| **회귀 ⑤-a live** | 선언 `target_branch` = 비-default(`mission-critical-trading-operating-system`) · D=∅ | **`PREVENTION_TARGET_MISMATCH`** | 1 | ⑤ D=∅ 에서도 red | **일치** |
| **회귀 ⑤-b live** | 선언 `owner_repo=octocat/Hello-World` | **`PREVENTION_TARGET_MISMATCH`** | 1 | ⑤ | **일치** |
| **회귀 ⑩-a live** | 원격 `https://gitlab.com/kakao-harris-lee/kis_unified_sts.git`(타 host 동일 경로) | **`PREVENTION_TARGET_MISMATCH`** — `계약 핀 … 과 일치하는 원격 부재` | 1 | ⑩ «host 를 버리는 정규화는 통과시킨다» | **일치** |
| **회귀 ⑩-b live** | 원격 `git@github.com:octocat/kis_unified_sts.git`(타 owner) | **`PREVENTION_TARGET_MISMATCH`** | 1 | ⑩ | **일치** |
| **회귀 ⑨-a** | `P_first→W→d→P_edit`(착수 «후» 아티팩트 편집) · 서버 seam | **`PREVENTION_ARTIFACT_MUTATED`** — `∀d P_first⊰d 이나 ∃d∈D: P_last=… ⋠ d` | 1 | ⑨ · 전순서 7 < 연속성 9 | **일치** |
| **본 저장소 live** | HEAD `d5a8302a` — 아티팩트 부재 | **`PREVENTION_ABSENT`** (수집: `ABSENT`(2)·`INSUFFICIENT`(5) → 2) | 1 | «현재 평가» | **일치 (인증 실측)** |
| **본 저장소 live + override** | 같은 실행에 `GH_HOST=example.invalid` | **`PREVENTION_ABSENT`** — 동일 | 1 | ⑫ live 불변 | **일치** |

**이 파일은 본 저장소의 `PREVENTION_ACTIVE` 를 주장하지 않는다** — live 관측값은 `INSUFFICIENT`·`TARGET_MISMATCH`·`ABSENT` 뿐이고 `ACTIVE` 는 전부 `SIMULATED` seam 이다.

---

## 1. 실행기 `u17-verify-v219.sh` — 원문 + 독해 선언 (sha256 `52dd03193f4e90ac1b369107ee7bd7301cca07b8ed8478d0a271ea48cd82d879`)

독해 선언(계약이 리터럴로 고정하지 않은 자리 · **v2.18e 실행기 대비 델타만** — 나머지는 `U17-PREVENTION-CHECK-V218-ADDENDUM.md` §3 독해가 그대로 유효하다):
- **[C6] host 결속**: `PIN_HOST` 를 계약 핀 `CANON` 의 host 성분에서 **파생**한다(`${CANON%%/*}` — 아티팩트 파라미터 아님). ① 전제 `gh auth status --hostname $PIN_HOST` — 실패면 `PREVENTION_UNVERIFIABLE` 발화(**타 host 폴백 없음**). ② `respond()` 의 `gh` 경로가 `gh api -i --hostname "$PIN_HOST" <path>` 로 나간다(적용 범위 = A00·A0·A1~A4·B1~B5 **전부**). ③ 프로세스 진입 직후 `export GH_HOST="$PIN_HOST"` 로 **자기 환경 재핀**하고, **재핀 «전» 상속값**을 `U17-H` 라인에 남긴다. ⑤ 응답 헤더를 `$CAP/<key>.hdr` 로 분리 보존하고 `X-GitHub-Request-Id` 를 매 캡처 라인에 병기한다.
- **[α] 연속성 소비자**: 입력우주 = `rules/branches/{target}` 응답의 `ruleset_id` 만(= «적용된» 룰셋 — `rulesets` 목록 전체가 아니다. `U17-α0` 라인이 둘을 병기한다). `t_land` = (b) 가 해석한 착지 PR 들의 서버 `merged_at` **문자열 최소**(ISO-8601 UTC 사전식 = 시각 순). `∀ 적용 룰셋`: `created_at ≤ t_land ∧ updated_at ≤ t_land` → 통과 / `created_at > t_land` → 차단(삭제-재생성 포함) / `updated_at > t_land` → 차단 / **타임스탬프 부재·파싱 불가 → 차단**(fail-closed). `D=∅` → vacuous. `D≠∅` 인데 `t_land` 미해석 → 차단(D-2 참조).
- **전순서 10단**: `rank()` 에 `PREVENTION_CONTINUITY_UNVERIFIABLE = 9` 를 넣고 `PREVENTION_ACTIVE` 는 10(발화 0일 때만 `finish` 가 방출).
- 나머지(C1·C2·C3·C4/R1·E1/E2/E3·(c-0) countersign 리터럴·responder seam·`trap EXIT` 폐쇄)는 v2.18e 와 **동일**하다.

```bash
#!/usr/bin/env bash
# u17-verify (v2.19) — U-17 «예방 통제 활성 증거» 실행기 (계약 d5a8302a §12.3.4 U-17)
#   v2.18e(feb91d60·sha256 6b196756…) 에서 파생 — 델타는 **C6 host 결속**과 **연속성 소비자**·**U-17-c 10값/전순서 10단** 뿐이다.
#   §12.3.4-R 하니스와 «별도». run 은 stdout 의 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다. CORR 은 이 run 을 보지 않는다.
#
#   [C3] 계약 핀 canonical_target = github.com/kakao-harris-lee/kis_unified_sts (계약 리터럴 · 아티팩트 파라미터 아님).
#        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관·E3 공존 허용). 부재 = TARGET_MISMATCH.
#        target = 핀 repo 의 `gh api --hostname <핀 host> repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «선택»[E2] — 있으면 대조·불일치 = TARGET_MISMATCH.
#   [C6 — v2.19 신설] **host 결속**: 핀 host = canonical_target 의 host 성분(github.com).  ① 전제 `gh auth status --hostname <핀 host>` 실패 → PREVENTION_UNVERIFIABLE
#        ② **모든** `gh api` 에 `--hostname <핀 host>` 명시  ③ 소비자 «자기 환경» `GH_HOST=<핀 host>` 재핀(플래그·환경 이중 결속 — `--hostname` 이 `GH_HOST` 를 이기는지에 의존하지 않는다)
#        ④ 도달·인증 불가는 **타 host 로 폴백하지 않는다**(fail-closed).  ⑤ 응답 헤더 `X-GitHub-Request-Id` 를 transcript 에 병기(보조 대조).
#   [C2] Actions app id 는 서버 파생: `gh api --hostname <핀 host> apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
#   (a) 술어 = v2.17 + [C1] required_status_checks.checks[] 의 <check> 컨텍스트 app_id == Actions app id (룰셋: required_status_checks[].integration_id == app id).
#   (b) ∀d∈D: pulls → merged ∧ base==target 인 PR head.sha → check-runs 에 name==check ∧ conclusion==success ∧ app.id==Actions ∧ head_sha==PR head 인 run;
#       check-suites/{run.check_suite.id}.head_sha == PR head [E2]; 워크플로 정체성 3중 [C2]: actions/runs?check_suite_id=<id> 의 run 중 head_sha==PR head 이고 path==.github/workflows/tos-gate.yml (계약 리터럴);
#       [R2·E1] `repos/{pin}/contents/.github/workflows/tos-gate.yml?ref=<PR head>` (서버 조회 · responder 경유) → base64 decode → 두 리터럴 `tools/tos_entry_harness.sh` · `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` grep.
#       404·기타 HTTP → UNVERIFIED_REVISION(검사 생략 금지) · 네트워크/인증(ERR) → UNVERIFIABLE. 로컬 `git show <head>:…` 는 보조 대조(선택·판정 미소비·U17-B5x 라인으로 기록만).
#   (α) [v2.19 신설 — 심판 F1] **연속성 소비자**(완료 판정 시점).  **서버 시간만 소비**한다 — 커밋 author/committer date 는 쓰지 않는다.
#       입력우주 = target 에 «적용된» 룰셋 s (`rules/branches/{target}` 의 ruleset_id → `rulesets/{id}`) · t_land = min{ merged_at(착지 PR) : d ∈ D }(서버 부여 값).
#       ∀ 적용 룰셋 s:  created_at ≤ t_land ∧ updated_at ≤ t_land → 그 축 통과 / created_at > t_land(삭제-재생성 포함) → CONTINUITY_UNVERIFIABLE / updated_at > t_land(off→on 토글 단조) → CONTINUITY_UNVERIFIABLE.
#       classic branch protection 만(적용 룰셋 부재) = 타임스탬프 부재 → CONTINUITY_UNVERIFIABLE.  타임스탬프 파싱 불가 → CONTINUITY_UNVERIFIABLE(fail-closed).
#       D = ∅ → 착지 대상 없음 = vacuous.  t_land 파생 불가(D≠∅ 인데 착지 PR 미해석) → CONTINUITY_UNVERIFIABLE(이 경우 (b) 가 이미 8 로 발화하므로 전순서상 8 이 이긴다).
#   (c) [C4/R1] P_first(최초 도입)·P_last(마지막 변경) 구조 파생(--full-history 후보 위): LATE = ∃d P_first⋠d · ARTIFACT_MUTATED = ∀d P_first⊰d ∧ ∃d P_last⋠d · ACTIVE 는 ∀d P_last⊰d ∧ HEAD blob == blob(P_last).
#   (c-0) countersign E3 리터럴.
#   전순서(U-17-c · 10값 · 차단 9): 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 CONTINUITY_UNVERIFIABLE > 10 ACTIVE.
#   ** 전 단계를 먼저 «수집»하고 마지막에 전순서 최소 순위를 방출한다 ** — (b) 의 조회 실패(1)가 (c) 의 LATE(6) 보다 먼저 성립하도록. exit 0 = ACTIVE 만. trap EXIT 폐쇄.
# 사용: bash u17-verify-v219.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
set -u -o pipefail
CANON=github.com/kakao-harris-lee/kis_unified_sts     # 계약 핀 (C3)
PIN_HOST=${CANON%%/*}                                 # [C6] 핀 host — 계약 핀에서 «파생»(아티팩트 선언 아님)
WF_PATH=.github/workflows/tos-gate.yml                # 계약 리터럴 (C2)
LIT1=tools/tos_entry_harness.sh                       # 계약 리터럴 (R2-i)
LIT2=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d   # 계약 리터럴 (R2-ii) — §12.3.4-R 블록 sha256
INHERITED_GH_HOST="${GH_HOST-∅(미설정)}"              # [C6] 재핀 «전» 상속값 기록
export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
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

# ── [C3] 핀·원격 대조 (host 보존 정규화)
PIN_OR=${CANON#*/}
norm_url() { printf '%s' "$1" | sed -E 's#^https?://([^/]+)/(.+)$#\1/\2#; s#^ssh://git@([^/]+)/(.+)$#\1/\2#; s#^git@([^:]+):(.+)$#\1/\2#; s#\.git$##; s#/$##'; }
REMOTES=$(git remote -v 2>/dev/null | awk '{print $1" "$2}' | sort -u)
MATCH_REMOTE=""; NORMED=""
while read -r rn ru; do [ -n "${ru:-}" ] || continue; n=$(norm_url "$ru"); NORMED="$NORMED $rn=$n"; [ "$n" = "$CANON" ] && MATCH_REMOTE="$rn"; done <<< "$REMOTES"

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
[ -z "$(yv host)" ]         || printf 'U17-note 아티팩트에 host 키가 있으나 v2.19 C6 는 host 를 «선언»에서 받지 않는다(무시) — 핀 파생값 %s 사용\n' "$PIN_HOST"
if [ -n "$BODY" ]; then
  MM=""   # [E2] 선언 키는 «선택» — 있으면 대조, 없으면 핀·API 파생이 유일 소스
  if [ -n "$DECL_OR" ]; then case "$DECL_OR" in "$CANON"|"$PIN_OR") ;; *) MM="$MM owner_repo(선언=$DECL_OR ≠ 핀=$CANON)";; esac; fi
  if [ -n "$DECL_TB" ] && [ -n "$TARGET" ] && [ "$DECL_TB" != "$TARGET" ]; then MM="$MM target_branch(선언=$DECL_TB ≠ 핀 repo default=$TARGET)"; fi
  printf 'U17-T declared-vs-pin: %s (declared owner_repo=%s target_branch=%s)\n' "${MM:-일치/선언 없음}" "${DECL_OR:-∅(선택 키 부재 → 핀 유일 소스)}" "${DECL_TB:-∅(선택 키 부재 → default_branch 유일 소스)}"
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
print("OK" if hit else "NO|paths=%s"%[(r.get("path"),r.get("head_sha","")[:7]) for r in runs])
PY
)
      [ "$WFOK" = OK ] || { IDENT_WHY="$IDENT_WHY workflow run path≠$WF_PATH ∨ head_sha≠PR head (${WFOK#NO|});"; continue; }
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
    L1=$(printf '%s\n' "$WF" | grep -cF -- "$LIT1"); L2=$(printf '%s\n' "$WF" | grep -cF -- "$LIT2")
    printf 'U17-B5 grep: %s → %s회 · %s → %s회\n' "$LIT1" "$L1" "$LIT2" "$L2"
    if git cat-file -e "$HSHA^{commit}" 2>/dev/null; then LB=$(git rev-parse -q --verify "$HSHA:$WF_PATH" 2>/dev/null || echo ABSENT); printf 'U17-B5x 보조(선택·판정 미소비): 로컬 git show %s:%s → %s\n' "$HSHA" "$WF_PATH" "$LB"; else printf 'U17-B5x 보조(선택·판정 미소비): 로컬에 %s 커밋 없음 — 서버 조회만으로 판정\n' "$HSHA"; fi
    { [ "$L1" -ge 1 ] && [ "$L2" -ge 1 ]; } || { fire PREVENTION_UNVERIFIED_REVISION "(b) d=$d head=$HSHA 서버 워크플로 blob 에 리터럴 부재 (harness path=$L1 sha256=$L2)"; continue; }
    printf 'U17-B d=%s head=%s merged_at=%s: name/conclusion/app.id=%s/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치\n' "$d" "$HSHA" "$MERGED" "$APPID"
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

finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```

### 1-2. `diff u17-verify-v218e.sh u17-verify-v219.sh` (직전 판 대비 델타 전문)

```diff
2c2,3
< # u17-verify (v2.18 에라타 feb91d60) — U-17 «예방 통제 활성 증거» 실행기 (계약 feb91d60 §12.3.4 U-17: C3 계약 핀·C1 checks[].app_id·C2 app id 서버 파생+워크플로 정체성 3중·**E1 R2 ③ 워크플로 blob 서버 조회**·E2 선언 키 선택·E3 원격 공존·C4/R1 P_first/P_last·U-17-c 9값/전순서 9단)
---
> # u17-verify (v2.19) — U-17 «예방 통제 활성 증거» 실행기 (계약 d5a8302a §12.3.4 U-17)
> #   v2.18e(feb91d60·sha256 6b196756…) 에서 파생 — 델타는 **C6 host 결속**과 **연속성 소비자**·**U-17-c 10값/전순서 10단** 뿐이다.
6,8c7,12
< #        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관). 부재 = TARGET_MISMATCH.
< #        target = 핀 repo 의 `gh api repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «대조 대상» — 핀/파생과 불일치 = TARGET_MISMATCH.
< #   [C2] Actions app id 는 서버 파생: `gh api apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
---
> #        git remote 는 «대조»: `git remote -v` 의 URL 을 host 보존 정규화(<host>/<owner>/<repo>)해 핀과 일치하는 원격이 «존재» 해야 한다(이름 무관·E3 공존 허용). 부재 = TARGET_MISMATCH.
> #        target = 핀 repo 의 `gh api --hostname <핀 host> repos/{pin}` .default_branch.  아티팩트 선언값(owner_repo·target_branch)은 «선택»[E2] — 있으면 대조·불일치 = TARGET_MISMATCH.
> #   [C6 — v2.19 신설] **host 결속**: 핀 host = canonical_target 의 host 성분(github.com).  ① 전제 `gh auth status --hostname <핀 host>` 실패 → PREVENTION_UNVERIFIABLE
> #        ② **모든** `gh api` 에 `--hostname <핀 host>` 명시  ③ 소비자 «자기 환경» `GH_HOST=<핀 host>` 재핀(플래그·환경 이중 결속 — `--hostname` 이 `GH_HOST` 를 이기는지에 의존하지 않는다)
> #        ④ 도달·인증 불가는 **타 host 로 폴백하지 않는다**(fail-closed).  ⑤ 응답 헤더 `X-GitHub-Request-Id` 를 transcript 에 병기(보조 대조).
> #   [C2] Actions app id 는 서버 파생: `gh api --hostname <핀 host> apps/github-actions` .id (gate_app_id 파라미터 폐지 — 아티팩트에 있어도 무시·기록).
13a18,22
> #   (α) [v2.19 신설 — 심판 F1] **연속성 소비자**(완료 판정 시점).  **서버 시간만 소비**한다 — 커밋 author/committer date 는 쓰지 않는다.
> #       입력우주 = target 에 «적용된» 룰셋 s (`rules/branches/{target}` 의 ruleset_id → `rulesets/{id}`) · t_land = min{ merged_at(착지 PR) : d ∈ D }(서버 부여 값).
> #       ∀ 적용 룰셋 s:  created_at ≤ t_land ∧ updated_at ≤ t_land → 그 축 통과 / created_at > t_land(삭제-재생성 포함) → CONTINUITY_UNVERIFIABLE / updated_at > t_land(off→on 토글 단조) → CONTINUITY_UNVERIFIABLE.
> #       classic branch protection 만(적용 룰셋 부재) = 타임스탬프 부재 → CONTINUITY_UNVERIFIABLE.  타임스탬프 파싱 불가 → CONTINUITY_UNVERIFIABLE(fail-closed).
> #       D = ∅ → 착지 대상 없음 = vacuous.  t_land 파생 불가(D≠∅ 인데 착지 PR 미해석) → CONTINUITY_UNVERIFIABLE(이 경우 (b) 가 이미 8 로 발화하므로 전순서상 8 이 이긴다).
15,16c24,25
< #   (c-0) countersign E3 리터럴.  (α) 룰셋 created_at/updated_at 관측(차단 아님).
< #   전순서: 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 ACTIVE.
---
> #   (c-0) countersign E3 리터럴.
> #   전순서(U-17-c · 10값 · 차단 9): 1 UNVERIFIABLE > 2 ABSENT > 3 UNSIGNED > 4 TARGET_MISMATCH > 5 INSUFFICIENT > 6 LATE > 7 ARTIFACT_MUTATED > 8 UNVERIFIED_REVISION > 9 CONTINUITY_UNVERIFIABLE > 10 ACTIVE.
18c27
< # 사용: bash u17-verify-v218.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
---
> # 사용: bash u17-verify-v219.sh [<repo-dir>]      (env: U17_RESPONDER=gh|file:<dir>|mixed:<dir> · U17_CAPTURE_DIR)
20a30
> PIN_HOST=${CANON%%/*}                                 # [C6] 핀 host — 계약 핀에서 «파생»(아티팩트 선언 아님)
23a34,35
> INHERITED_GH_HOST="${GH_HOST-∅(미설정)}"              # [C6] 재핀 «전» 상속값 기록
> export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
35c47
< rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; *) echo 99;; esac; }
---
> rank() { case "$1" in PREVENTION_UNVERIFIABLE) echo 1;; PREVENTION_ABSENT) echo 2;; PREVENTION_UNSIGNED) echo 3;; PREVENTION_TARGET_MISMATCH) echo 4;; PREVENTION_INSUFFICIENT) echo 5;; PREVENTION_LATE) echo 6;; PREVENTION_ARTIFACT_MUTATED) echo 7;; PREVENTION_UNVERIFIED_REVISION) echo 8;; PREVENTION_CONTINUITY_UNVERIFIABLE) echo 9;; *) echo 99;; esac; }
40c52
< # ── responder seam
---
> # ── responder seam  ([C6] gh 경로의 모든 조회에 --hostname <핀 host> 명시 · 헤더 별도 보존)
42c54
<   local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body"
---
>   local path="$1" k; k=$(key "$1"); local st="$CAP/$k.status" bd="$CAP/$k.body" hd="$CAP/$k.hdr"
44c56,57
<     gh)  local out; out=$(gh api -i "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
---
>     gh)  local out; out=$(gh api -i --hostname "$PIN_HOST" "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
>          printf '%s\n' "$out" | awk '/^\r?$/{exit} {print}' | tr -d '\r' > "$hd"
48,49c61,62
<          if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
<          else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; return 1; fi ;;
---
>          if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
>          else printf 'ERR\n' > "$st"; printf 'SIMULATED responder: no injected response for %s\n' "$path" > "$bd"; : > "$hd"; return 1; fi ;;
51c64
<          if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
---
>          if [ -f "$dir/$k.status" ]; then cp "$dir/$k.status" "$st"; cp "$dir/$k.body" "$bd" 2>/dev/null || : > "$bd"; : > "$hd"; printf 'U17-seam %s ← file(SIMULATED)\n' "$path"; grep -Eq '^[0-9]{3}$' "$st" && return 0; return 1
56c69,70
< show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")"; sed 's/^/  | /' "$CAP/$k.body"; }
---
> reqid() { grep -i '^X-GitHub-Request-Id:' "$CAP/$(key "$1").hdr" 2>/dev/null | head -1 | tr -d '\r' | sed 's/^[Xx]-[Gg]it[Hh]ub-[Rr]equest-[Ii]d:[[:space:]]*//'; }
> show_capture() { local k; k=$(key "$2"); printf 'U17-%s %s  utc=%s  http=%s  x-github-request-id=%s\n' "$1" "$2" "$(utc)" "$(cat "$CAP/$k.status")" "$(reqid "$2")"; sed 's/^/  | /' "$CAP/$k.body"; }
73a88,92
> # ── [C6 ①] 전제: 핀 host 인증  (responder=file 은 live 조회가 없으므로 SIMULATED 로 기록만)
> AUTHRC=0; AUTHOUT=""; AUTHMODE=live
> AUTHCMD="gh auth status --hostname $PIN_HOST"                     # [C6] 표시·사유 문자열 (대조군은 이 줄과 다음 줄이 함께 바뀐다)
> case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status --hostname "$PIN_HOST" 2>&1); AUTHRC=$? ;; esac
> 
79c98,101
< show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "${TARGET:-∅}"
---
> printf 'U17-H [C6] pin_host=%s (계약 핀에서 파생) · 상속 GH_HOST=%s → 현행 GH_HOST=%s · auth 전제 `%s` → mode=%s rc=%s\n' "$PIN_HOST" "$INHERITED_GH_HOST" "${GH_HOST-∅(재핀 없음)}" "$AUTHCMD" "$AUTHMODE" "$AUTHRC"
> if [ "$AUTHMODE" = live ]; then printf '%s\n' "$AUTHOUT" | sed 's/^/  | /'; else printf '  | (responder=%s — live 조회 없음: 주입 응답 위 결정적 술어)\n' "$RESP"; fi
> [ "$AUTHMODE" != live ] || [ "$AUTHRC" -eq 0 ] || fire PREVENTION_UNVERIFIABLE "[C6] \`$AUTHCMD\` 실패(rc=$AUTHRC) — 핀 host 인증 부재 (타 host 폴백 없음)"
> show_capture A00 "apps/github-actions"; printf 'U17-A0 repos/%s  utc=%s  http=%s  x-github-request-id=%s  (.default_branch=%s)\n' "$PIN_OR" "$(utc)" "$ST0" "$(reqid "repos/$PIN_OR")" "${TARGET:-∅}"
89a112
> [ -z "$(yv host)" ]         || printf 'U17-note 아티팩트에 host 키가 있으나 v2.19 C6 는 host 를 «선언»에서 받지 않는다(무시) — 핀 파생값 %s 사용\n' "$PIN_HOST"
102a126
> APPLIED_IDS=""
107a132,140
> # [α] 연속성 입력우주 = target 에 «적용된» 룰셋만 (rules/branches/{target} 의 ruleset_id) — rulesets 목록 전체가 아니다
> APPLIED_IDS=$(python3 -c 'import json,sys
> ids=[]
> try:
>     a=json.load(open(sys.argv[1]))
>     for r in a if isinstance(a,list) else []:
>         if isinstance(r,dict) and r.get("ruleset_id") is not None and str(r["ruleset_id"]) not in ids: ids.append(str(r["ruleset_id"]))
> except Exception: pass
> print(" ".join(ids))' "$CAP/$(key "$P_RULES").body" 2>/dev/null)
119c152
< for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; printf 'U17-α ruleset %s created_at=%s updated_at=%s enforcement=%s (관측 기록)\n' "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$(jget "repos/$PIN_OR/rulesets/$id" enforcement)"; done
---
> for id in $RSIDS; do respond "repos/$PIN_OR/rulesets/$id"; show_capture A4 "repos/$PIN_OR/rulesets/$id"; done
120a154
> printf 'U17-α0 적용 룰셋(연속성 입력우주) = [%s]  (rules/branches/%s 의 ruleset_id · rulesets 목록 전체=[%s])\n' "$(printf '%s' "$APPLIED_IDS")" "$TARGET" "$(printf '%s' "$RSIDS")"
202a237
> MINMERGED=""
206d240
<   MINMERGED=""
282,283c316,332
<   for id in ${RSIDS:-}; do
<     python3 - "$id" "$(jget "repos/$PIN_OR/rulesets/$id" created_at)" "$(jget "repos/$PIN_OR/rulesets/$id" updated_at)" "$MINMERGED" <<'PY'
---
> fi
> 
> # ── (α) [v2.19 — 심판 F1] 연속성 소비자 (전순서 9) — «서버 시간»만 소비한다
> if [ "$ND" -eq 0 ]; then
>   printf 'U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)\n'
> elif [ -z "$TARGET" ]; then
>   printf 'U17-α target 미파생 — 연속성 평가 불가 (전순서 1 이 이미 발화)\n'
> elif [ -z "$MINMERGED" ]; then
>   fire PREVENTION_CONTINUITY_UNVERIFIABLE "t_land 파생 불가(D≠∅ 이나 착지 PR 의 서버 merged_at 미해석) — 연속성 판정 불가"
> else
>   printf 'U17-α t_land = min{merged_at(착지 PR) : d∈D} = %s  (서버 부여 값만 · 커밋 author/committer date 불신)\n' "$MINMERGED"
>   if [ -z "$APPLIED_IDS" ]; then
>     fire PREVENTION_CONTINUITY_UNVERIFIABLE "적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가"
>   else
>     for id in $APPLIED_IDS; do
>       CA=$(jget "repos/$PIN_OR/rulesets/$id" created_at); UA=$(jget "repos/$PIN_OR/rulesets/$id" updated_at)
>       CONT=$(python3 - "$id" "$CA" "$UA" "$MINMERGED" <<'PY'
290,291c339,343
< if None in (c,u,m): print(f"U17-α ruleset {i}: 시각 파싱 불가(created_at={ca} updated_at={ua} merged_at(minD)={mm}) — 관측 기록"); sys.exit(0)
< print(f"U17-α ruleset {i}: created_at={c.isoformat()} {'≤' if c<=m else '> (착수 후 생성)'} merged_at(minD)={m.isoformat()} · updated_at={u.isoformat()} {'> merged_at (착수 후 변경됨)' if u>m else '≤ merged_at'} (관측 기록·차단 아님)")
---
> if m is None: print("BLOCK|t_land 파싱 불가(merged_at=%s)"%mm); sys.exit(0)
> if c is None or u is None: print("BLOCK|ruleset %s 서버 타임스탬프 부재·파싱 불가(created_at=%s updated_at=%s) — 연속성 판정 불가"%(i,ca,ua)); sys.exit(0)
> if c>m: print("BLOCK|ruleset %s created_at=%s > t_land=%s — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호"%(i,c.isoformat(),m.isoformat())); sys.exit(0)
> if u>m: print("BLOCK|ruleset %s updated_at=%s > t_land=%s — 착지 후 «설정 변경»(off→on 토글도 updated_at 단조 증가) · benign/malign 구별 불가"%(i,u.isoformat(),m.isoformat())); sys.exit(0)
> print("PASS|ruleset %s created_at=%s ≤ t_land ∧ updated_at=%s ≤ t_land"%(i,c.isoformat(),u.isoformat()))
293c345,349
<   done
---
> )
>       printf 'U17-α ruleset %s: %s\n' "$id" "${CONT#*|}"
>       case "$CONT" in BLOCK\|*) fire PREVENTION_CONTINUITY_UNVERIFIABLE "(α) ${CONT#*|} — 운영자 재심사 경로(영구 차단 아님)";; esac
>     done
>   fi
296c352
< finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND · app/suite/workflow path/blob 2 리터럴) — responder=$RESP"
---
> finish "(a) 술어 충족(checks[].app_id==Actions $APPID) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname $PIN_HOST · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=$ND) ∧ (α) 연속성 성립(t_land=${MINMERGED:-∅}) — responder=$RESP"
```

## 2. 대조군 실행기 `u17-verify-v219-CTRL-nohost.sh` — 생성 규칙 + diff (sha256 `c24bf96f0df70fd12724284e8667effd71181e2e71f27be06863586c4c4c0b7a`)

**판정용이 아니다.** v2.19 실행기에서 **세 자리만** 제거해 v2.18 거동(host 를 `gh` 환경에 위임)을 재현한다 — 그래서 «델타 = host 결속»임이 파일 수준에서 증명된다. 생성 명령(재현):

```bash
sed -e 's/gh api -i --hostname "$PIN_HOST" /gh api -i /' \
    -e 's/^export GH_HOST="$PIN_HOST".*$/# [대조군] GH_HOST 재핀 «제거» — host 를 gh 환경에 위임 (v2.18 거동)/' \
    -e 's/^AUTHCMD="gh auth status --hostname $PIN_HOST".*$/AUTHCMD="gh auth status"                                           # [대조군] host 미명시/' \
    -e 's/gh auth status --hostname "$PIN_HOST" 2>&1/gh auth status 2>\&1/' \
    -e 's/^# u17-verify (v2.19).*$/# u17-verify-v219-CTRL-nohost — …/' \
    u17-verify-v219.sh > u17-verify-v219-CTRL-nohost.sh
```

```diff
2c2
< # u17-verify (v2.19) — U-17 «예방 통제 활성 증거» 실행기 (계약 d5a8302a §12.3.4 U-17)
---
> # u17-verify-v219-CTRL-nohost — [T-84 ⑫ 대조군] v2.19 실행기에서 «--hostname 명시»·«GH_HOST 재핀»·«auth 전제의 --hostname» 만 제거한 변형 (v2.18 거동 재현). 판정용 아님.
35c35
< export GH_HOST="$PIN_HOST"                            # [C6] ③ 소비자 자기 환경 재핀 (플래그·환경 이중 결속)
---
> # [대조군] GH_HOST 재핀 «제거» — host 를 gh 환경에 위임 (v2.18 거동)
56c56
<     gh)  local out; out=$(gh api -i --hostname "$PIN_HOST" "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
---
>     gh)  local out; out=$(gh api -i "$path" 2>"$CAP/$k.err"); printf '%s\n' "$out" | awk 'NR==1{print $2; exit}' > "$st"
90,91c90,91
< AUTHCMD="gh auth status --hostname $PIN_HOST"                     # [C6] 표시·사유 문자열 (대조군은 이 줄과 다음 줄이 함께 바뀐다)
< case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status --hostname "$PIN_HOST" 2>&1); AUTHRC=$? ;; esac
---
> AUTHCMD="gh auth status"                                           # [대조군] host 미명시
> case "$RESP" in file:*) AUTHMODE=simulated ;; *) AUTHOUT=$(gh auth status 2>&1); AUTHRC=$? ;; esac
```

## 3. 드라이버 원문 — `t84v219.sh` (sha256 `75bef9a3d9a652e9f4761324c83bcc14a7d36a41c4b103df5fcaf7c8ae5a15a2`)

```bash
#!/usr/bin/env bash
# t84v219.sh — v2.19 T-84 ⑪(연속성 SIMULATED (a)~(f)) · ⑫(GH_HOST override live) + 회귀(③ ACTIVE seam · ⑤⑩ live TARGET_MISMATCH · ⑨ ARTIFACT_MUTATED) 드라이버.
# GET-only(gh api 조회만) · 서버 쓰기·설정 변경 0 · 픽스처는 scratchpad 독립 git repo(본 저장소 무접촉·worktree 미사용).
set -u
SP=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence
EX="$SP/u17-verify-v219.sh"; CTRL="$SP/u17-verify-v219-CTRL-nohost.sh"; EX218="$SP/u17-verify-v218e.sh"
FX="$SP/fx84z"; SEAM="$SP/seam219"
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
wfcontent(){ printf 'name: tos-gate\non: [pull_request]\njobs:\n  tos-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: verify harness identity\n        run: shasum -a 256 tools/tos_entry_harness.sh | grep %s\n      - name: run entry harness\n        run: bash tools/tos_entry_harness.sh\n' "$LIT2"; }
wf(){ mkdir -p "$1/.github/workflows"; wfcontent > "$1/$WF"; git -C "$1" add -A; git -C "$1" commit -q -m "W: add $WF (SIMULATED)"; git -C "$1" rev-parse HEAD; }
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
rev_seam(){ # rev_seam <dir> <d> <head> <suite> <merged_at|NOPR>
  local dir="$1" d="$2" h="$3" s="$4" m="$5"
  if [ "$m" = NOPR ]; then inject "$dir" "repos/$OR/commits/$d/pulls" 200 '[]'; return; fi
  inject "$dir" "repos/$OR/commits/$d/pulls" 200 "[{\"number\":9999,\"state\":\"closed\",\"merged_at\":\"$m\",\"base\":{\"ref\":\"main\"},\"head\":{\"sha\":\"$h\"}}]"
  inject "$dir" "repos/$OR/commits/$h/check-runs" 200 "{\"total_count\":2,\"check_runs\":[{\"name\":\"test\",\"conclusion\":\"success\",\"app\":{\"id\":15368},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}},{\"name\":\"tos-gate\",\"conclusion\":\"success\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"head_sha\":\"$h\",\"check_suite\":{\"id\":$s}}]}"
  inject "$dir" "repos/$OR/check-suites/$s" 200 "{\"id\":$s,\"head_sha\":\"$h\",\"app\":{\"id\":15368,\"slug\":\"github-actions\"},\"status\":\"completed\",\"conclusion\":\"success\"}"
  inject "$dir" "repos/$OR/actions/runs?check_suite_id=$s" 200 "{\"total_count\":1,\"workflow_runs\":[{\"id\":424242,\"name\":\"tos-gate\",\"path\":\"$WF\",\"head_sha\":\"$h\",\"check_suite_id\":$s,\"conclusion\":\"success\"}]}"
  wfcontent > "$dir/wf.txt"; inject "$dir" "repos/$OR/contents/$WF?ref=$h" 200 "$(contents_json "$dir/wf.txt" "$(git hash-object "$dir/wf.txt")" "$WF")"; }

rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't84v219_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'sha256(u17-verify-v219.sh)=%s\n' "$(shasum -a 256 "$EX" | cut -d" " -f1)"
printf 'sha256(u17-verify-v219-CTRL-nohost.sh)=%s\n' "$(shasum -a 256 "$CTRL" | cut -d" " -f1)"
printf 'sha256(u17-verify-v218e.sh)=%s   (직전 판 실행기 — ⑪ 판별력 대조용)\n' "$(shasum -a 256 "$EX218" | cut -d" " -f1)"

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
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=$DBG bash u17-verify-v219.sh <fixture>   # utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
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
sec "⑪ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · 이후 (a)~(f) 는 seam 만 바뀐다"
RC="$FX/cont"; mk "$RC"; art "$RC" "$OR" main >/dev/null; WHEAD=$(wf "$RC"); DCOM=$(d0a "$RC")
echo "W(PR head)=$WHEAD  d=$DCOM"

sec "T-84 ⑪-(a) SIMULATED — 정상: 적용 룰셋 created_at·updated_at ≤ t_land($TLAND) → PREVENTION_ACTIVE"
S="$SEAM/a"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(b) SIMULATED — off→merge→on: updated_at(2026-08-11) > t_land($TLAND) → PREVENTION_CONTINUITY_UNVERIFIABLE"
S="$SEAM/b"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-11T09:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(b') 판별력 대조 — 같은 (b) seam 을 «직전 판» 실행기(u17-verify-v218e.sh)로 실행 → 연속성 미소비라 통과해야 한다(= v2.19 가 닫은 자리)"
run "$RC" "file:$S" "$EX218"

sec "T-84 ⑪-(c) SIMULATED — 삭제-재생성: 새 id 77 · created_at(2026-08-12) > t_land → PREVENTION_CONTINUITY_UNVERIFIABLE"
S="$SEAM/c"; seam_ruleset "$S" 77 2026-08-12T00:00:00Z 2026-08-12T00:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(d) SIMULATED — classic-only(적용 룰셋 0 · protection 은 (a) 술어 충족) → 타임스탬프 부재 → PREVENTION_CONTINUITY_UNVERIFIABLE"
S="$SEAM/d"; seam_classic "$S"; rev_seam "$S" "$DCOM" "$WHEAD" 777001 "$TLAND"; run "$RC" "file:$S"

sec "T-84 ⑪-(d') 판별력 대조 — 같은 (d) seam 을 직전 판 실행기로 → classic-only 로 ACTIVE (v2.18 은 연속성을 묻지 않는다)"
run "$RC" "file:$S" "$EX218"

sec "T-84 ⑪-(e) SIMULATED — direct-push(착지 PR 없음): (b) UNVERIFIED_REVISION(8) 이 연속성(9) 보다 «먼저» 발화해야 한다 (룰셋 updated_at 은 t_land 이후로 둔다)"
S="$SEAM/e"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-11T09:00:00Z; rev_seam "$S" "$DCOM" "$WHEAD" 777001 NOPR; run "$RC" "file:$S"

sec "T-84 ⑪-(f) SIMULATED — committer-date 무시 대조: (a) 와 같은 seam 인데 픽스처 커밋 시각을 2026-12-31 로 «미래»에 둔다 → 상태값 불변(ACTIVE) 이어야 한다"
RF="$FX/cont-latedate"; mk "$RF"
GIT_AUTHOR_DATE="2026-12-31T00:00:00Z" GIT_COMMITTER_DATE="2026-12-31T00:00:00Z" art "$RF" "$OR" main >/dev/null
WHEAD2=$(GIT_AUTHOR_DATE="2026-12-31T01:00:00Z" GIT_COMMITTER_DATE="2026-12-31T01:00:00Z" wf "$RF")
DCOM2=$(GIT_AUTHOR_DATE="2026-12-31T02:00:00Z" GIT_COMMITTER_DATE="2026-12-31T02:00:00Z" d0a "$RF")
echo "W=$WHEAD2 d=$DCOM2 (모든 커밋 author/committer date = 2026-12-31, t_land=$TLAND 보다 «늦다»)"
S="$SEAM/f"; seam_ruleset "$S" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S" "$DCOM2" "$WHEAD2" 777001 "$TLAND"; run "$RF" "file:$S"

########################################################################
sec "회귀 ③ — (b) 양성 SIMULATED seam 에서 PREVENTION_ACTIVE (룰셋 경로 · ⑪-(a) 와 동일 구성)  [v2.19 하 ACTIVE 도달 경로]"
echo "  (⑪-(a) run 이 그 자체로 ③ ACTIVE SIMULATED seam 이다 — 재실행으로 극성을 고정한다)"
S="$SEAM/a"; run "$RC" "file:$S"

sec "회귀 ③-classic — v2.18 의 ③-b 양성 구성(classic protection 만)을 v2.19 실행기로 → 연속성 축에서 접힌다 (관측 보고 대상)"
S="$SEAM/d"; run "$RC" "file:$S" | tail -8

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
sec "본 저장소 현행 상태 — live (실측 음성) · HEAD d5a8302a"
echo "\$ bash u17-verify-v219.sh $REPO"; U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO"; echo "u17_rc=$?"

sec "본 저장소 현행 상태 — GH_HOST=example.invalid override 하 (상태값 불변 확인)"
echo "\$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy bash u17-verify-v219.sh $REPO   (요약)"
env GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_CAPTURE_DIR="$(mktemp -d)" bash "$EX" "$REPO" | grep -E '^U17-H|^u17_live_state|^u17_live_reason|^prevention_control_state|^reason'; echo "u17_rc=${PIPESTATUS[0]}"
```

## 4. 실행 기록 (`bash t84v219.sh` stdout 전문 · 캡처 verbatim + UTC · rc 포함)

각 run 은 `U17-0 target=<owner>/<repo>@<branch>` 라인이 연다(§12.3.4 (d) · U-15-e (4c-2) 확장). run 당 상태 라인은 `prevention_control_state=` **정확히 1개**이며, transcript 는 발행 시점에 확정되고 이후 편집하지 않는다((4d)).

```text
t84v219_utc=2026-08-19T01:03:19Z
sha256(u17-verify-v219.sh)=52dd03193f4e90ac1b369107ee7bd7301cca07b8ed8478d0a271ea48cd82d879
sha256(u17-verify-v219-CTRL-nohost.sh)=c24bf96f0df70fd12724284e8667effd71181e2e71f27be06863586c4c4c0b7a
sha256(u17-verify-v218e.sh)=6b196756890f580058c38c4b8e1f44e39c95c1b4137a33377af2602ad414a15c   (직전 판 실행기 — ⑪ 판별력 대조용)

########## A. [C6] 원시 host 프로브 — 심판 실측 프로브 재현 (실행기 밖 · GET-only) ##########
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts --jq .default_branch    # utc=2026-08-19T01:03:19Z
  | * Request to https://api.github.com/repos/kakao-harris-lee/kis_unified_sts
  | > GET /repos/kakao-harris-lee/kis_unified_sts HTTP/1.1
  | > Host: api.github.com
  | < HTTP/2.0 200 OK
  | * Request took 438.9015ms
  | main
  ⇒ --hostname 이 GH_HOST 를 이긴다: 요청 host = api.github.com

$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api gh api repos/kakao-harris-lee/kis_unified_sts --jq .default_branch    # (--hostname 없음 = v2.18 거동)  utc=2026-08-19T01:03:19Z
  | * Request to https://example.invalid/api/v3/repos/kakao-harris-lee/kis_unified_sts
  | > GET /api/v3/repos/kakao-harris-lee/kis_unified_sts HTTP/1.1
  | > Host: example.invalid
  | * dial tcp: lookup example.invalid: no such host
  | * Request took 1.907166ms
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
  * 2d6ccef 2026-08-19T10:03:19+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 077494d 2026-08-19T10:03:19+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.4vu7Vu8skW
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:03:21Z  http=200  x-github-request-id=7EB1:11185E:14A31C:174C4E:6A8500D8
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:21Z  http=200  x-github-request-id=5C8F:328E21:13F491:169D62:6A8500D9  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:22Z  http=200  x-github-request-id=6270:335F3A:144645:16EF7F:6A8500DA
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:22Z  http=200  x-github-request-id=8A7F:19934D:13E431:168D8D:6A8500DA
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:23Z  http=200  x-github-request-id=6CB3:177308:13D07C:1679BE:6A8500DB
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:03:24Z  http=200  x-github-request-id=544E:11185E:14A6C8:175041:6A8500DB
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 P_last=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 |D|=0 D= 
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
  * 2d6ccef 2026-08-19T10:03:19+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 077494d 2026-08-19T10:03:19+09:00 seed
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.cc5v5OE20H
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:03:26Z  http=200  x-github-request-id=A18B:94A79:13D093:167AB5:6A8500DD
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:26Z  http=200  x-github-request-id=C07D:346330:1412BA:16BB6F:6A8500DD  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:26Z  http=200  x-github-request-id=E044:1DEFCF:142F66:16D948:6A8500DE
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:27Z  http=200  x-github-request-id=776E:21B9D:1498CA:1742D8:6A8500DF
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:27Z  http=200  x-github-request-id=D306:328E21:13FBEB:16A574:6A8500DF
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:03:28Z  http=200  x-github-request-id=064C:328E21:13FCA8:16A62F:6A8500E0
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 P_last=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑫-3 live — override 하에서 실행기가 실제로 어느 host 로 갔는가 (GH_DEBUG=api 요청 host 캡처) ##########
  주: 실행기는 gh 의 stderr 를 $U17_CAPTURE_DIR/<key>.err 로 보내므로 GH_DEBUG 출력은 그 파일에 남는다 — 실행 후 전수 grep 한다.
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6lQyuFhWOK bash u17-verify-v219.sh <fixture>   # utc=2026-08-19T01:03:28Z
  (u17_rc=1)
$ grep -h '^\* Request to\|^> Host:' /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6lQyuFhWOK/*.err | sort | uniq -c
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
  * 2d6ccef 2026-08-19T10:03:19+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 077494d 2026-08-19T10:03:19+09:00 seed
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy U17_RESPONDER=gh bash u17-verify-v219-CTRL-nohost.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@UNRESOLVED
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=∅ (apps/github-actions http=ERR) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.7u1my69wjU
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
U17-A00 apps/github-actions  utc=2026-08-19T01:03:34Z  http=ERR  x-github-request-id=
  | error connecting to example.invalid
  | check your internet connection or https://githubstatus.com
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:34Z  http=ERR  x-github-request-id=  (.default_branch=∅)
U17-fire PREVENTION_UNVERIFIABLE: apps/github-actions 조회 실패(http=ERR) — Actions app id 파생 불가
U17-fire PREVENTION_UNVERIFIABLE: repos/kakao-harris-lee/kis_unified_sts 조회 실패(http=ERR) — default_branch 파생 불가
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
P_first=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 P_last=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_UNVERIFIABLE
reason=[C6] `gh auth status` 실패(rc=1) — 핀 host 인증 부재 (타 host 폴백 없음) [수집 3건 중 전순서 최소]
u17_rc=1

########## T-84 ⑫-5 대조군 host 캡처 — 대조군은 실제로 example.invalid 로 나간다 ##########
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy GH_DEBUG=api U17_CAPTURE_DIR=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1Mu0PtEnWs bash u17-verify-v219-CTRL-nohost.sh <fixture>   # utc=2026-08-19T01:03:34Z
  (u17_rc=1)
$ grep -h '^\* Request to\|^> Host:' /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1Mu0PtEnWs/*.err | sort | uniq -c
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
  * 2d6ccef 2026-08-19T10:03:19+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 077494d 2026-08-19T10:03:19+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219-CTRL-nohost.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.DNbhiREwJs
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
U17-A00 apps/github-actions  utc=2026-08-19T01:03:38Z  http=200  x-github-request-id=4745:201076:1432A5:16DDA3:6A8500E9
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:38Z  http=200  x-github-request-id=3AC6:21B9D:14A588:175139:6A8500EA  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:39Z  http=200  x-github-request-id=77FA:94A79:13E10D:168CFA:6A8500EA
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:39Z  http=200  x-github-request-id=53ED:346330:142277:16CD1D:6A8500EB
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:40Z  http=200  x-github-request-id=3C9F:C76AD:141385:16BED2:6A8500EB
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:03:40Z  http=200  x-github-request-id=E747:33C891:141EBD:16CB19:6A8500EC
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 P_last=2d6ccefc3cfb56bac0c09f88ec030734ac8adab2 |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_INSUFFICIENT
reason=(a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0] [수집 1건 중 전순서 최소]
u17_rc=1

########## ⑪ 픽스처 저장소 — P(아티팩트) → W(워크플로) → d(D0-A 착수) · 이후 (a)~(f) 는 seam 만 바뀐다 ##########
W(PR head)=c2d3436a7d145d19bc754688f32079daee0460d8  d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2

########## T-84 ⑪-(a) SIMULATED — 정상: 적용 룰셋 created_at·updated_at ≤ t_land(2026-08-10T00:00:00Z) → PREVENTION_ACTIVE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.3Brd2Sgm4e
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:41Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:41Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:41Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:42Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:43Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a
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
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.hqLUs5fNJd
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:43Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:43Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:44Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:44Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:45Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:45Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
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
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tdvrPBAiLh
U17-A00 apps/github-actions  utc=2026-08-19T01:03:45Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:45Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:45Z  http=404
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:45Z  http=200
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:46Z  http=200
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:46Z  http=200
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α ruleset 42 created_at=2026-08-01T00:00:00Z updated_at=2026-08-11T09:00:00Z enforcement=active (관측 기록)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:46Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:46Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:46Z  http=200
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:46Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:46Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α ruleset 42: created_at=2026-08-01T00:00:00+00:00 ≤ merged_at(minD)=2026-08-10T00:00:00+00:00 · updated_at=2026-08-11T09:00:00+00:00 > merged_at (착수 후 변경됨) (관측 기록·차단 아님)
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/b
u17_rc=0

########## T-84 ⑪-(c) SIMULATED — 삭제-재생성: 새 id 77 · created_at(2026-08-12) > t_land → PREVENTION_CONTINUITY_UNVERIFIABLE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/c bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/c capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1Vjj6PiZCG
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/c — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:47Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:47Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:47Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:47Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":77,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":77},{"type":"non_fast_forward","ruleset_id":77},{"type":"deletion","ruleset_id":77}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:48Z  http=200  x-github-request-id=
  | [{"id":77,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-12T00:00:00Z","updated_at":"2026-08-12T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/77  utc=2026-08-19T01:03:48Z  http=200  x-github-request-id=
  | {"id":77,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-12T00:00:00Z","updated_at":"2026-08-12T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [77]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[77])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:48Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:48Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:49Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:49Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:49Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 77: ruleset 77 created_at=2026-08-12T00:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: (α) ruleset 77 created_at=2026-08-12T00:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호 — 운영자 재심사 경로(영구 차단 아님)
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=(α) ruleset 77 created_at=2026-08-12T00:00:00+00:00 > t_land=2026-08-10T00:00:00+00:00 — 룰셋이 «착지 후»에 생김(삭제-재생성 포함) = 그 착지는 비보호 — 운영자 재심사 경로(영구 차단 아님) [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑪-(d) SIMULATED — classic-only(적용 룰셋 0 · protection 은 (a) 술어 충족) → 타임스탬프 부재 → PREVENTION_CONTINUITY_UNVERIFIABLE ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.jDwwk8uW0S
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:50Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:50Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:50Z  http=200  x-github-request-id=
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:50Z  http=200  x-github-request-id=
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:50Z  http=200  x-github-request-id=
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:51Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:51Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:51Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:51Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:51Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: 적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가 [수집 1건 중 전순서 최소]
u17_rc=1

########## T-84 ⑪-(d') 판별력 대조 — 같은 (d) seam 을 직전 판 실행기로 → classic-only 로 ACTIVE (v2.18 은 연속성을 묻지 않는다) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d bash u17-verify-v218e.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.vSWYDPafpa
U17-A00 apps/github-actions  utc=2026-08-19T01:03:52Z  http=200
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:52Z  http=200  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:52Z  http=200
  | {"url":"SIMULATED","required_status_checks":{"strict":true,"contexts":["tos-gate"],"checks":[{"context":"tos-gate","app_id":15368}]},"required_pull_request_reviews":{"dismiss_stale_reviews":true,"required_approving_review_count":1},"enforce_admins":{"enabled":true},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:52Z  http=200
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:52Z  http=200
  | []
U17-A4 (ruleset 0 — rulesets/{id} 조회 대상 없음)
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=True ruleset=False
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:52Z  http=200
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:52Z  http=200
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:52Z  http=200
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:53Z  http=200
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:53Z  http=200
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1 · app/suite/workflow path/blob 2 리터럴) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/d
u17_rc=0

########## T-84 ⑪-(e) SIMULATED — direct-push(착지 PR 없음): (b) UNVERIFIED_REVISION(8) 이 연속성(9) 보다 «먼저» 발화해야 한다 (룰셋 updated_at 은 t_land 이후로 둔다) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/e bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/e capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.tdpy7YiOYX
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/e — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:53Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:53Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:53Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:54Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:54Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:54Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-11T09:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:54Z  http=200  x-github-request-id=
  | []
U17-fire PREVENTION_UNVERIFIED_REVISION: (b) d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 착지 PR 부재·merged 아님·base≠target (pulls=0)
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: t_land 파생 불가(D≠∅ 이나 착지 PR 의 서버 merged_at 미해석) — 연속성 판정 불가
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b) d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 착지 PR 부재·merged 아님·base≠target (pulls=0) [수집 2건 중 전순서 최소]
u17_rc=1

########## T-84 ⑪-(f) SIMULATED — committer-date 무시 대조: (a) 와 같은 seam 인데 픽스처 커밋 시각을 2026-12-31 로 «미래»에 둔다 → 상태값 불변(ACTIVE) 이어야 한다 ##########
W=ae214c5646e9ed11889df527cc1c18637bc0882b d=d12d40c5e2827e4849fcbf051fdefb4d6a45c58f (모든 커밋 author/committer date = 2026-12-31, t_land=2026-08-10T00:00:00Z 보다 «늦다»)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * d12d40c 2026-12-31T02:00:00+00:00 D0-A: introduce config/tos_completion.yaml
  * ae214c5 2026-12-31T01:00:00+00:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * d7848d7 2026-12-31T00:00:00+00:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 7d191bd 2026-08-19T10:03:54+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/f bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/f capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.O0LA9OMTao
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/f — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:55Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:55Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:55Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:55Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:55Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=d7848d764997b1d786c453d60bc48dd72778ba08 P_last=d7848d764997b1d786c453d60bc48dd72778ba08 |D|=1 D=d12d40c5e2827e4849fcbf051fdefb4d6a45c58f 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/d12d40c5e2827e4849fcbf051fdefb4d6a45c58f/pulls  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"ae214c5646e9ed11889df527cc1c18637bc0882b"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/ae214c5646e9ed11889df527cc1c18637bc0882b/check-runs  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"ae214c5646e9ed11889df527cc1c18637bc0882b","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"ae214c5646e9ed11889df527cc1c18637bc0882b","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"ae214c5646e9ed11889df527cc1c18637bc0882b","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"ae214c5646e9ed11889df527cc1c18637bc0882b","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=ae214c5646e9ed11889df527cc1c18637bc0882b  utc=2026-08-19T01:03:56Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@ae214c5646e9ed11889df527cc1c18637bc0882b (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show ae214c5646e9ed11889df527cc1c18637bc0882b:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d12d40c5e2827e4849fcbf051fdefb4d6a45c58f head=ae214c5646e9ed11889df527cc1c18637bc0882b merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/f
u17_rc=0

########## 회귀 ③ — (b) 양성 SIMULATED seam 에서 PREVENTION_ACTIVE (룰셋 경로 · ⑪-(a) 와 동일 구성)  [v2.19 하 ACTIVE 도달 경로] ##########
  (⑪-(a) run 이 그 자체로 ③ ACTIVE SIMULATED seam 이다 — 재실행으로 극성을 고정한다)
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 327fb6f 2026-08-19T10:03:41+09:00 D0-A: introduce config/tos_completion.yaml
  * c2d3436 2026-08-19T10:03:41+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 529bdec 2026-08-19T10:03:41+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * b595f77 2026-08-19T10:03:41+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.0Mh0yonRY8
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:03:57Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:03:57Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:03:57Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:03:57Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:03:57Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:03:57Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=529bdec924f38192afd774edf39a53900d95200f P_last=529bdec924f38192afd774edf39a53900d95200f |D|=1 D=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2/pulls  utc=2026-08-19T01:03:58Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"c2d3436a7d145d19bc754688f32079daee0460d8"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/c2d3436a7d145d19bc754688f32079daee0460d8/check-runs  utc=2026-08-19T01:03:58Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:03:58Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:03:58Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"c2d3436a7d145d19bc754688f32079daee0460d8","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=c2d3436a7d145d19bc754688f32079daee0460d8  utc=2026-08-19T01:03:58Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@c2d3436a7d145d19bc754688f32079daee0460d8 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ ∀d∈D: P_last ⊰ d ∧ HEAD blob==P_last blob ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/a
u17_rc=0

########## 회귀 ③-classic — v2.18 의 ③-b 양성 구성(classic protection 만)을 v2.19 실행기로 → 연속성 축에서 접힌다 (관측 보고 대상) ##########
U17-B5 grep: tools/tos_entry_harness.sh → 2회 · 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d → 1회
U17-B5x 보조(선택·판정 미소비): 로컬 git show c2d3436a7d145d19bc754688f32079daee0460d8:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=327fb6fe98fc9e080d8941ca7cf1dd33d4c1ddd2 head=c2d3436a7d145d19bc754688f32079daee0460d8 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-fire PREVENTION_CONTINUITY_UNVERIFIABLE: 적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가
prevention_control_state=PREVENTION_CONTINUITY_UNVERIFIABLE
reason=적용 룰셋 0 = classic branch protection 만 → protection 응답에 created_at·updated_at 부재 → 연속성 판정 불가 [수집 1건 중 전순서 최소]
u17_rc=1

########## 회귀 ⑤-a live — 선언 target=비-default 브랜치 → PREVENTION_TARGET_MISMATCH ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: mission-critical-trading-operating-system
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * 08140d3 2026-08-19T10:04:00+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 074de1a 2026-08-19T10:04:00+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.LVfxfWRXQb
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:04:02Z  http=200  x-github-request-id=E1B8:328E21:14233B:16D0FC:6A850101
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:02Z  http=200  x-github-request-id=1BC9:94A79:13FB4A:16A9E3:6A850102  (.default_branch=main)
U17-T declared-vs-pin:  target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main) (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=mission-critical-trading-operating-system)
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: target_branch(선언=mission-critical-trading-operating-system ≠ 핀 repo default=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:03Z  http=200  x-github-request-id=9156:335F3A:147546:172380:6A850103
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:03Z  http=200  x-github-request-id=B4B8:328E21:14257A:16D381:6A850103
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:04Z  http=200  x-github-request-id=F89F:177308:13FCBC:16AB04:6A850104
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:04:05Z  http=200  x-github-request-id=9519:94A79:13FDF7:16ACB8:6A850104
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=08140d3bfd9185c584cb8a2947d49b372e8bfdc3 P_last=08140d3bfd9185c584cb8a2947d49b372e8bfdc3 |D|=0 D= 
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
  * b97843d 2026-08-19T10:04:05+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 949af8b 2026-08-19T10:04:05+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.XloLzRnbDT
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:04:07Z  http=200  x-github-request-id=E64F:C76AD:1431D3:16E02C:6A850106
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:07Z  http=200  x-github-request-id=84FE:1D7764:13E87E:16972F:6A850106  (.default_branch=main)
U17-T declared-vs-pin:  owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts) (declared owner_repo=octocat/Hello-World target_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 아티팩트 선언값이 계약 핀/파생값과 불일치: owner_repo(선언=octocat/Hello-World ≠ 핀=github.com/kakao-harris-lee/kis_unified_sts)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:08Z  http=200  x-github-request-id=2DE1:11185E:14DDA2:178C74:6A850107
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:10Z  http=200  x-github-request-id=995F:33C891:143FED:16EFCA:6A85010A
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:11Z  http=200  x-github-request-id=B6BE:335F3A:147DAB:172CD8:6A85010A
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:04:11Z  http=200  x-github-request-id=8BA6:177308:140537:16B460:6A85010B
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=b97843d3ba4cc82696731bbee50ebd6b27c81571 P_last=b97843d3ba4cc82696731bbee50ebd6b27c81571 |D|=0 D= 
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
  * 495704c 2026-08-19T10:04:12+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * acac96e 2026-08-19T10:04:12+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=gitlab.com/kakao-harris-lee/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.lr1UYJZ1uK
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:04:13Z  http=200  x-github-request-id=35B0:1DEFCF:1468D5:171868:6A85010C
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:14Z  http=200  x-github-request-id=E238:C76AD:143A66:16E9B1:6A85010D  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=gitlab.com/kakao-harris-lee/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:14Z  http=200  x-github-request-id=9731:201076:145CD1:170C14:6A85010E
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:15Z  http=200  x-github-request-id=3FBD:198918:14213F:16D148:6A85010E
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:15Z  http=200  x-github-request-id=A1EF:21B9D:14D29A:178260:6A85010F
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:04:16Z  http=200  x-github-request-id=BF38:328E21:143401:16E35E:6A85010F
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=495704c8547c5e1d8360eed31742a9cceb2bd682 P_last=495704c8547c5e1d8360eed31742a9cceb2bd682 |D|=0 D= 
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
  * 38715db 2026-08-19T10:04:16+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * 0ba1571 2026-08-19T10:04:16+09:00 seed
$ U17_RESPONDER=gh bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/octocat/kis_unified_sts match=∅ | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.6VTolGCeOg
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:04:19Z  http=200  x-github-request-id=29CE:328E21:143633:16E5C8:6A850111
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:19Z  http=200  x-github-request-id=1207:19934D:14220A:16D22F:6A850112  (.default_branch=main)
U17-fire PREVENTION_TARGET_MISMATCH: 계약 핀 github.com/kakao-harris-lee/kis_unified_sts 과 일치하는 원격 부재 (git remote -v 정규화: origin=github.com/octocat/kis_unified_sts)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:19Z  http=200  x-github-request-id=8D17:346330:14504F:16FF6F:6A850113
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:20Z  http=200  x-github-request-id=55E2:346330:1450F3:170026:6A850113
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:20Z  http=200  x-github-request-id=217C:389700:142306:16D37F:6A850114
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:04:21Z  http=200  x-github-request-id=5E17:11185E:14EE11:179E87:6A850114
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=38715dbb7836731063aea7ed65d7ce8d16625c3a P_last=38715dbb7836731063aea7ed65d7ce8d16625c3a |D|=0 D= 
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
  * cc02d17 2026-08-19T10:04:22+09:00 P_edit: artifact edited after D0-A start (SIMULATED)
  * d546b7a 2026-08-19T10:04:21+09:00 D0-A: introduce config/tos_completion.yaml
  * 940953e 2026-08-19T10:04:21+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 2ad16e6 2026-08-19T10:04:21+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * d634e27 2026-08-19T10:04:21+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/mut bash u17-verify-v219.sh <fixture>
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/mut capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.I77yGr81g2
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/seam219/mut — live 조회 없음: 주입 응답 위 결정적 술어)
U17-A00 apps/github-actions  utc=2026-08-19T01:04:22Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:22Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main)
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:22Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:22Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:22Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T01:04:22Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first=2ad16e6276fbe7ed7021283a700d976137fd3bd5 P_last=cc02d176660be528d4498ad2956006f8cd444306 |D|=1 D=d546b7a1c56d95789736a22037f066a7079dc3c6 
U17-fire PREVENTION_ARTIFACT_MUTATED: ∀d P_first⊰d 이나 ∃d∈D: P_last=cc02d176660be528d4498ad2956006f8cd444306 ⋠ d — 착수 «후» 아티팩트 변경
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/d546b7a1c56d95789736a22037f066a7079dc3c6/pulls  utc=2026-08-19T01:04:23Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"940953e874faad74e2020d65cefb80009d2bbb57"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/940953e874faad74e2020d65cefb80009d2bbb57/check-runs  utc=2026-08-19T01:04:23Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"940953e874faad74e2020d65cefb80009d2bbb57","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"940953e874faad74e2020d65cefb80009d2bbb57","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T01:04:23Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"940953e874faad74e2020d65cefb80009d2bbb57","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T01:04:23Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"940953e874faad74e2020d65cefb80009d2bbb57","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=940953e874faad74e2020d65cefb80009d2bbb57  utc=2026-08-19T01:04:23Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "0aefd2ab57db63d19548f877328f66bef3a45100", "size": 365, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSB1c2VzOiBhY3Rpb25zL2NoZWNrb3V0QHY0CiAgICAgIC0gbmFtZTogdmVyaWZ5IGhhcm5lc3MgaWRlbnRpdHkKICAgICAgICBydW46IHNoYXN1bSAtYSAyNTYgdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2ggfCBncmVwIDk1N2JmNDlkYThmYzZhZTM5Zjk3YWJlNjc5NDExYWZlYWE1YTU5ZjcwN2YzNWJmM2IzYThjNmY5ZGUxNDFmMGQKICAgICAgLSBuYW1lOiBydW4gZW50cnkgaGFybmVzcwogICAgICAgIHJ1bjogYmFzaCB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaAo=\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@940953e874faad74e2020d65cefb80009d2bbb57 (encoding=base64 size=365):
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
U17-B5x 보조(선택·판정 미소비): 로컬 git show 940953e874faad74e2020d65cefb80009d2bbb57:.github/workflows/tos-gate.yml → 0aefd2ab57db63d19548f877328f66bef3a45100
U17-B d=d546b7a1c56d95789736a22037f066a7079dc3c6 head=940953e874faad74e2020d65cefb80009d2bbb57 merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/server-blob(2 리터럴) 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ARTIFACT_MUTATED
reason=∀d P_first⊰d 이나 ∃d∈D: P_last=cc02d176660be528d4498ad2956006f8cd444306 ⋠ d — 착수 «후» 아티팩트 변경 [수집 1건 중 전순서 최소]
u17_rc=1

########## 본 저장소 현행 상태 — live (실측 음성) · HEAD d5a8302a ##########
$ bash u17-verify-v219.sh /Users/harris/Development/private/kis_unified_sts
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=gh capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.ixXMrXKCIw
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
  | github.com
  |   ✓ Logged in to github.com account kakao-harris-lee (keyring)
  |   - Active account: true
  |   - Git operations protocol: https
  |   - Token: gho_************************************
  |   - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
U17-A00 apps/github-actions  utc=2026-08-19T01:04:25Z  http=200  x-github-request-id=B401:19934D:14299F:16DA75:6A850118
  | {"id":15368,"client_id":"Iv1.05c79e9ad1f6bdfa","slug":"github-actions","node_id":"MDM6QXBwMTUzNjg=","owner":{"login":"github","id":9919,"node_id":"MDEyOk9yZ2FuaXphdGlvbjk5MTk=","avatar_url":"https://avatars.githubusercontent.com/u/9919?v=4","gravatar_id":"","url":"https://api.github.com/users/github","html_url":"https://github.com/github","followers_url":"https://api.github.com/users/github/followers","following_url":"https://api.github.com/users/github/following{/other_user}","gists_url":"https://api.github.com/users/github/gists{/gist_id}","starred_url":"https://api.github.com/users/github/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/github/subscriptions","organizations_url":"https://api.github.com/users/github/orgs","repos_url":"https://api.github.com/users/github/repos","events_url":"https://api.github.com/users/github/events{/privacy}","received_events_url":"https://api.github.com/users/github/received_events","type":"Organization","user_view_type":"public","site_admin":false},"name":"GitHub Actions","description":"Automate your workflow from idea to production","external_url":"https://help.github.com/en/actions","html_url":"https://github.com/apps/github-actions","created_at":"2018-07-30T09:30:17Z","updated_at":"2026-06-18T16:17:48Z","permissions":{"actions":"write","administration":"read","artifact_metadata":"write","attestations":"write","checks":"write","code_quality":"write","contents":"write","copilot_requests":"write","deployments":"write","discussions":"write","drives":"write","issues":"write","merge_queues":"write","metadata":"read","models":"read","packages":"write","pages":"write","pull_requests":"write","repository_hooks":"write","repository_projects":"write","security_events":"write","statuses":"write","vulnerability_alerts":"read"},"events":["branch_protection_rule","check_run","check_suite","create","delete","deployment","deployment_status","discussion","discussion_comment","fork","gollum","issues","issue_comment","label","merge_group","milestone","page_build","public","pull_request","pull_request_review","pull_request_review_comment","push","registry_package","release","repository","repository_dispatch","status","watch","workflow_dispatch","workflow_run"]}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T01:04:25Z  http=200  x-github-request-id=81F2:33C891:1451DC:17036E:6A850119  (.default_branch=main)
U17-fire PREVENTION_ABSENT: 아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T01:04:26Z  http=200  x-github-request-id=3885:335F3A:148EE0:173FC3:6A85011A
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enabled":false},"required_conversation_resolution":{"enabled":false},"lock_branch":{"enabled":false},"allow_fork_syncing":{"enabled":false}}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T01:04:26Z  http=200  x-github-request-id=CE91:198918:142EA3:16DFE7:6A85011A
  | []
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T01:04:27Z  http=200  x-github-request-id=1BD0:328E21:144125:16F1CA:6A85011B
  | [{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682  utc=2026-08-19T01:04:28Z  http=200  x-github-request-id=E42C:177308:14180F:16C901:6A85011B
  | {"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","conditions":{"ref_name":{"exclude":[],"include":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00","bypass_actors":[],"current_user_can_bypass":"never","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}}}
U17-α0 적용 룰셋(연속성 입력우주) = []  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[17017682])
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
U17-fire PREVENTION_INSUFFICIENT: (a) classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
P_first=∅ P_last=∅ |D|=0 D= 
U17-B D=∅ — (b)(c) 검증 대상 없음 (계약 #6: (a) ∧ 핀/target 대조 만으로 판정)
U17-α D=∅ — 착지 대상 없음 = 연속성 vacuous ((b) 와 동일)
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1

########## 본 저장소 현행 상태 — GH_HOST=example.invalid override 하 (상태값 불변 확인) ##########
$ GH_HOST=example.invalid GH_ENTERPRISE_TOKEN=dummy bash u17-verify-v219.sh /Users/harris/Development/private/kis_unified_sts   (요약)
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=example.invalid → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=live rc=0
u17_live_state=PREVENTION_INSUFFICIENT
u17_live_reason=classic:[contexts∌tos-gate; strict≠true; enforce_admins≠true; required_pull_request_reviews 키 부재] ruleset:[적용 규칙 0]
prevention_control_state=PREVENTION_ABSENT
reason=아티팩트 HEAD 부재: tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md [수집 2건 중 전순서 최소]
u17_rc=1
```

---
## 5. 관측 보고 · 계약 결함 후보 (고치지 않는다 — `bound_paths` 동결 · 에라타 대상)

### D-1 (실질) — (a) 술어의 «classic disjunct» 와 연속성 소비자가 충돌한다: `D ≠ ∅` 이면 classic 경로로 `PREVENTION_ACTIVE` 도달 불가

- **문언**: (a) 술어는 classic branch protection 과 룰셋 동등물을 **선택지(disjunct)** 로 둔다 — 계약 `:5220`(술어 머리) ~ `:5236`(«(룰셋 동등물일 때) enforcement == "active"»). 즉 «classic 만으로도 (a) 충족» 이 명시적으로 가능하다.
- **그런데** 연속성 소비자는 `:5443` 에서 «classic branch protection 만(룰셋 부재) → protection 응답에 `created_at`·`updated_at` 이 «없다» → 연속성 판정 불가 → `CONTINUITY_UNVERIFIABLE`» 이고, `U-17-c` 의 `PREVENTION_ACTIVE`(`:5504`)는 «(a) ∧ (b) ∧ **연속성 성립**» 의 논리곱이다.
- **귀결**: **`D ≠ ∅` 인 모든 구성에서 classic disjunct 는 死분기다** — (a) 를 통과해도 (α) 가 항상 9 를 발화한다. 실측 §4 «회귀 ③-classic»: **v2.18 증거의 ③-b 양성 구성(classic protection 만)이 v2.19 실행기에서 `PREVENTION_CONTINUITY_UNVERIFIABLE`/1 로 접힌다**(v2.18 에서는 `PREVENTION_ACTIVE`/0 이었다 — ⑪-(d′) 대조가 같은 seam 에서 직전 판 실행기로 `ACTIVE` 를 재현한다).
- **왜 결함 후보인가**: 계약은 이 귀결을 **어디에도 적지 않았다**. «룰셋만이 연속성을 증명할 수 있으므로 운영자는 룰셋으로 보호해야 한다»가 **의도**라면 (a) 의 classic disjunct 옆에 그렇게 적어야 하고, 의도가 아니라면 (α) 가 classic 을 다르게 다뤄야 한다. 지금은 **선언(«동등물»)과 도달 가능성이 갈린다** — v2.14 `G4` 가 폐기한 «사코드 분기» 클래스와 같은 형태이며, v2.18 `R1` 이 `ARTIFACT_MUTATED` 에서 고친 것과 동형이다.
- **비고**: 본 저장소 현행은 애초에 `INSUFFICIENT` 라 live 로는 드러나지 않는다 — SIMULATED 로만 관측된다.

### D-2 (문언 공백) — `t_land` 파생 불가 시 (α) 의 처분이 미정의

- `:5433` 은 `t_land = min{ merged_at(pr) }` 를 «(PR 객체의 «서버 부여» `merged_at` 만 쓴다 — `D≠∅` 이고 (b) 통과 시 실재)» 로 적는다. **(b) 가 통과하지 못해 `t_land` 를 못 뽑는 경우의 (α) 상태는 적혀 있지 않다.**
- 실행기는 fail-closed 로 `PREVENTION_CONTINUITY_UNVERIFIABLE`(9)을 발화했고, 전순서상 (b) 의 8 이 이겨 **방출값은 바뀌지 않았다**(⑪-(e) 실측: 수집 8·9 → 8). 극성은 안전하나 **문언에는 그 자리가 없다.**

### D-3 (관측) — «적용 룰셋» 과 «룰셋 목록» 이 실측에서 갈린다

- (α) 입력우주는 `:5432` 대로 **`rules/branches/{target}` → `rulesets/{id}`**(= «적용된» 룰셋)이다. 본 저장소 실측은 `rules/branches/main = []` 인데 `rulesets = [{id 17017682, "protect_main", enforcement "disabled", created_at/updated_at 2026-05-29}]` 이다 ⇒ **룰셋이 «실재»하는데 «적용»은 0** 이라 (α) 입력우주는 공집합이고, 그 룰셋의 타임스탬프는 연속성에 **소비되지 않는다**. 문언대로의 거동이나, «룰셋이 있는데 classic-only 로 접힘»이라는 상태가 존재함을 기록한다(D-1 과 결합하면 `ACTIVE` 도달 경로가 더 좁아진다).

### D-4 (정직 경계 — 실증 한계) — «타 host 응답으로 `PREVENTION_ACTIVE` 위조» 는 **직접 실증하지 못했다**

- `:5199` 부근 C6 는 «타 GitHub Enterprise/mock host 의 보호·앱 응답으로 `PREVENTION_ACTIVE` 를 위조할 수 있다»고 적는다. 본 실행은 **GET-only·서버 쓰기 0** 규율상 응답을 주는 타 host 를 세울 수 없으므로, 실증은 **«대조군이 실제로 타 host 로 나간다»**(⑫-5: `2 * Request to https://example.invalid/…`)와 **«핀 실행기는 6/6 요청이 `api.github.com`»**(⑫-3)까지다. 위조 ACTIVE 자체는 **심판 프로브(exit 1)와 같은 수준의 간접 증거**이며, 그 이상은 아니다 — 숨기지 않는다.

### D-5 (관측) — `--hostname` 이 `GH_HOST` 를 이긴다 (gh 2.93.0 실측)

- §4 A 프로브: `GH_HOST=example.invalid` + `--hostname github.com` → `Host: api.github.com`. 즉 **이 gh 버전에서는 «플래그·환경 이중 결속» 중 플래그만으로도 충분**하다. 계약이 «우선순위에 «의존하지 않는» 이중 결속»(`:5207` 부근)을 요구한 것은 **버전 의존을 피하려는 규율**이고, 실측은 그 규율이 지금 판에서 과잉이 아님을 증명하지도 반증하지도 않는다(현재 버전에서 두 결속이 «같은 방향»이라 구별 불가). 정직 기록.

### D-6 (독해 선언 — 문언 미규정) — `responder=file:`(SIMULATED) 에서의 auth 전제

- C6 ①은 `gh auth status --hostname <핀 host>` 를 **전제**로 두지만, v2.16 이 도입한 **«캡처된 응답 위 결정적 술어» seam** 에서는 live 조회 자체가 없다. 실행기는 `responder=file:*` 일 때 auth 전제를 **SIMULATED 로 기록만** 하고 발화하지 않는다(`U17-H … mode=simulated`). `mixed:`·`gh` 는 live 로 수행한다. **계약이 두 층의 상호작용을 적지 않아 독해로 채운 자리**다.

### D-7 (관측) — 아티팩트의 `host` 키

- C3 규율(«선언하지 않으면 고를 수 없다»)에 따라 실행기는 아티팩트에 `host:` 키가 있어도 **무시하고 기록만** 한다(`U17-note`). 계약이 `gate_app_id`·`remote_name` 은 «폐지»로 명시했으나 `host` 는 **애초에 도입된 적이 없어 폐지 문구도 없다** — 미래 아티팩트가 그 키를 넣었을 때의 처분이 문언에 없다. 실행기는 fail-closed 방향(무시)으로 읽었다.

---
## 6. 사후 검증 원문 (repo 무영향 · HEAD 불변 · 서버 설정 무변경 · S-24 재확인 · 픽스처 격리)

```text
post_utc=2026-08-19T01:15:17Z
$ git -C <repo> rev-parse HEAD
d5a8302a6c33d54e58a0556e59b6c85860059847
$ git -C <repo> status --short
 M uv.lock
?? tools/spikes/
$ git -C <repo> diff --quiet d5a8302a -- <계약>  → rc
rc=0
$ git -C <repo> rev-list --count d5a8302a..HEAD -- <계약>
0
$ git -C <repo> show d5a8302a:<계약> | sed -n '4589,4689p' | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ sed -n '4589,4689p' <워킹트리 계약> | shasum -a 256
957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d  -
$ git -C <repo> reflog -n 3
d5a8302a HEAD@{0}: commit: docs(tos): phase0 completion contract v2.19 — continuity consumer, host-bound queries, structural c_APP, U-16-d total order, dev-plan amendment proposal
8a533c5e HEAD@{1}: commit: docs(reviews): record lane B v2.18 re-adjudication — NOT_PASSED (F1/F2/F4 partial · F3 resolved · F5 evaded · new 2)
81d532ff HEAD@{2}: commit: docs(tos): re-binding (current cycle) — OQ-11 disposition bound to frozen v2.18
--- 서버 설정 무변경 재조회 (GET-only · 진입 시점과 동일한가) ---
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection   # utc=2026-08-19T01:15:17Z
{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks/contexts","checks":[{"context":"test","app_id":15368}]},"required_signatures":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_signatures","enabled":false},"enforce_admins":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/enforce_admins","enabled":false},"required_linear_history":{"enabled":false},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false},"block_creations":{"enab
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rules/branches/main   # utc=2026-08-19T01:15:18Z
[]
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rulesets   # utc=2026-08-19T01:15:18Z
[{"id":17017682,"name":"protect_main","target":"branch","source_type":"Repository","source":"kakao-harris-lee/kis_unified_sts","enforcement":"disabled","node_id":"RRS_lACqUmVwb3NpdG9yec5D1X_dzgEDq1I","_links":{"self":{"href":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682"},"html":{"href":"https://github.com/kakao-harris-lee/kis_unified_sts/rules/17017682"}},"created_at":"2026-05-29T15:33:46.629+09:00","updated_at":"2026-05-29T15:33:46.662+09:00"}]
$ gh api --hostname github.com repos/kakao-harris-lee/kis_unified_sts/rulesets/17017682 --jq '{id,enforcement,created_at,updated_at,bypass_actors}'
{"bypass_actors":[],"created_at":"2026-05-29T15:33:46.629+09:00","enforcement":"disabled","id":17017682,"updated_at":"2026-05-29T15:33:46.662+09:00"}
--- 픽스처 격리 확인 ---
$ ls -d /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82z
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx82z
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z
$ git -C /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v219-evidence/fx84z/host-base remote -v (원격 URL 은 로컬 config 만 — push/fetch 0)
origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
$ find <scratchpad fixtures> -name .git -maxdepth 3 | wc -l
      20
```

**판독**: HEAD `d5a8302a` 불변 · 계약 워킹트리 = 동결 blob(`git diff --quiet` rc=0) · `d5a8302a..HEAD` 계약 커밋 0 · 하니스 블록 sha256 동결/워킹트리 **byte-동일** · 워킹트리 변경은 실행 «전»부터 있던 `uv.lock`·`tools/spikes/` 뿐(본 실행이 만든 것 0) · 서버 3 엔드포인트 재조회가 진입 시점과 **동일**(`protection` strict=false·contexts=["test"] · `rules/branches/main`=[] · `rulesets` 1건 `disabled`, `created_at`/`updated_at` 2026-05-29 불변) ⇒ **서버 쓰기·설정 변경 0** · 픽스처 git 저장소 20개는 전부 scratchpad 하위다.
