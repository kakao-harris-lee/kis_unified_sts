# U17-PREVENTION-CHECK-V221-ADDENDUM — S-24 재결속 (v2.21 **에라타 재동결 `65cf2635`**)

- **비규범 부속**. 계약·개발계획을 바꾸지 않는다. 선행 증거 `U17-PREVENTION-CHECK-V221.md`(커밋 `3e0f2429`)는 **(4d) 불변** — 재결속은 이 파일로 한다.
- 생성 UTC `2026-08-19T12:36:26Z` · 서버 쓰기·설정 변경 **0** · GitHub 는 **GET-only**(사후 재조회 1회 · §6) · 픽스처는 scratchpad **독립 git 저장소**(본 저장소 무접촉·worktree 미사용).

## 0. 결속 선언 (실측 §6 원문)

| 항목 | 실측 |
| --- | --- |
| HEAD | `65cf26353d310a8f48a2bd1fce0cedb3de81b4fa` == `65cf2635` |
| 계약 워킹트리 blob | `2660b800ab04a2536bdeaa3bf86168b65667b78d` == `git show 65cf2635:<계약>` |
| 개발계획 blob | `4b2f664f835c4f3c68e4dff8560214aaa70f8969` == `0528a919` 동결본 (**에라타에서 무변경**) |
| `65cf2635..HEAD` | 두 문서 커밋 **0** · 전체 커밋 **0** |
| 하니스 `sed -n '4664,4764p'` | sha256 `957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d` — 계약 리터럴 일치 ∧ `0528a919` 과 **byte-동일** |
| 계약 행수 | 7,531 (동결과 동일 · 인라인 +5/-5) |

## 1. S-24 ① — 무엇이 바뀌었고, 무엇이 닿지 않았나

### 1-1. 계약 차분 원문 (`git diff -U0 0528a919..65cf2635 -- <계약>`)

```diff
diff --git a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
index d9d45793..2660b800 100644
--- a/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
+++ b/docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
@@ -130 +130 @@
-> | **v2.21** | **재심 미착수.** v2.20 판정 2건(#1 U-17 (b)③ 회피 — «정본 대조» 재설계[1차 (iii) AST 는 독립 검증 C FAIL] · #2 #5/#6 비순환 생산 순서)을 반영한 판이며, **개발계획에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 연장). **동결 → 증거 → (필요 시 에라타) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
+> | **v2.21** | **재심 미착수.** v2.20 판정 2건(#1 U-17 (b)③ 회피 — «정본 대조» 재설계[1차 (iii) AST 는 독립 검증 C FAIL] · #2 #5/#6 비순환 생산 순서)을 반영한 판이며, **개발계획에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 연장). **동결(`0528a919`) → 증거(`3e0f2429` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ 적발) → 에라타 재동결(문언·과잉 차단 방향) → 운영자 재결속(현행 사이클)** 대기다. 재결속 전에는 심사를 요청하지 않는다(§12.3.2) |
@@ -213 +213 @@
-| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`false && bash tools/…`·`exit 0; bash tools/…`(선행 종결자) 도달 불가 호출이 전부 `PREVENTION_ACTIVE`. **1차 (iii) 셸 AST 요건은 독립 검증 C FAIL**(B10 `set -euo pipefail; exit 0; bash …`·B11 `exec true`·B12 `[ ] && exit 0` — «선행 종결자»를 「`&&` 피연산자」 규칙이 미포섭·런타임 미실행 실증) → 폐기. **운영자 «바퀴 재발명 금지» 지침(CLAUDE.md Development Discipline) 적용해 «정본 대조»로 재설계**: 게이트 두 스텝 `run:` 을 정규화(CRLF→LF·trailing 공백·빈 줄·full-line 주석 제거) 후 계약 «정본»(정본 A `set -euo pipefail` + `bash tools/tos_entry_harness.sh` / 정본 B `set -euo pipefail` + `printf %s…\n <sha> | shasum -a 256 -c -`)과 byte 대조 — 다르면 UNVERIFIED_REVISION. 정본 대조는 «정본과 다르면 전부»라 exit/exec/가드/서브셸/heredoc/eval/무효화/선행 종결자 전 구문 우회를 «열거 없이» 닫는다(열린→닫힌 세계·S-6). YAML 파싱+byte 대조 = 기존 도구·자작 파서/도달성 분석기 불요. 스텝 메타(shell·continue-on-error·if·timeout)는 닫힌 키 집합. 정본 B 는 sha 불일치 시 `shasum -c` 비-0→`set -euo pipefail` 스텝 실패로 실패 전파 보장(실측 정상 OK/0·변조 FAILED/1). **T-84 ⑬ 재편 = «정본 불일치 클래스»**(⑬a echo·⑬b trailing 주석·⑬c `|| true`·⑬d 도달 불가 호출·⑬e continue-on-error/if·⑬f set +e/trap·**⑬g 선행 종결자**·전부 정본 불일치→UNVERIFIED_REVISION·종수 불변) + 양성(정본 일치) + 정규화 대조군(주석/공백만 다르면 일치). **정직 경계**: 정본 일치 ≠ 런타임 실제 실행(선행 스텝 `PATH`/`env` 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함). ② **#2 #5/#6 부분 (medium) — 비순환 생산 순서**: 활성 UNCHK-008 owner_track 이 `Phase 1`·U-17 하니스 경로가 «D0-A 산출물»이라 Phase 0 가 PREVENTION_ACTIVE 를 소비하기 전에 그 축·하니스를 누가 산출·폐쇄하는지 단일 비순환 순서 부재((D) verbatim 적용이 활성 형제 소비처 미전파·S-22). **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 착수 전 선행조건·운영자/인프라·U-17 live 검증·문법 n∈0..7 유효·imprecise_owner_track 불변[단일 phase])·산문 2곳(:4975·:5102) 전파 · **U-17 하니스 «D0-A 산출물»→«pre-D0-A 실체화»**(§12.3.4-R 결속값 sha 957bf49d… 파일 실체화·D0-A 착수 «전» 운영자/인프라가 둔다) · **개발계획 Phase 0 선행조건 불릿에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 «연장»·같은 대상·같은 pre-D0-A 주체·(D) ②′ verbatim 재기록). **S-22 전수**: «D0-A 산출물» 표기 중 하니스 파일(:5462)만 정정(U15-ENTRY-CHECK·config·원장·계약텍스트는 유지)·UNCHK-023(브랜치 보호 계열이나 git 이력 신뢰 별개 축이라 `Phase 1` 유지)·형제 UNCHK 행 재독. **종수 전파(S-20)**: T-84 14 불변(⑬c 검출 전환·⑬d/e/f 는 ⑬ 하위 케이스)·T-82 20·T-81 19·U-17-c 10값·U-16-d 12단 불변. **§12.3.3**: (A)=v2.20 판정 5건 리터럴(회피 1·해소 3·부분 1)·(B)=v2.21 2건 주장(«어느 것도 해소 아님»·#1 실행 증거 동결 후·#2 형제 전파+개발계획 연장)·(D) 갱신(②′ 연장). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·현행 :4664-4764)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
+| **v2.21** | **v2.20 심판 판정 2건(high 1 / medium 1) 전건 반영. 직전 처분은 «#1 회피 · #2·#3·#4 해소(아크 누적 11) · #5/#6 부분» 이다.** ① **#1 U-17 (b)③ (high, 회피) — 정본 대조 재설계**: v2.20 구조 파서+서버 스텝이 «토큰 존재·이름/conclusion»만 인증해 `|| true`·`set +e`·`false && bash tools/…`·`exit 0; bash tools/…`(선행 종결자) 도달 불가 호출이 전부 `PREVENTION_ACTIVE`. **1차 (iii) 셸 AST 요건은 독립 검증 C FAIL**(B10 `set -euo pipefail; exit 0; bash …`·B11 `exec true`·B12 `[ ] && exit 0` — «선행 종결자»를 「`&&` 피연산자」 규칙이 미포섭·런타임 미실행 실증) → 폐기. **운영자 «바퀴 재발명 금지» 지침(CLAUDE.md Development Discipline) 적용해 «정본 대조»로 재설계**: 게이트 두 스텝 `run:` 을 정규화(CRLF→LF·trailing 공백·빈 줄·full-line 주석 제거) 후 계약 «정본»(정본 A `set -euo pipefail` + `bash tools/tos_entry_harness.sh` / 정본 B `set -euo pipefail` + `printf %s…\n <sha> | shasum -a 256 -c -`)과 byte 대조 — 다르면 UNVERIFIED_REVISION. 정본 대조는 «정본과 다르면 전부»라 exit/exec/가드/서브셸/heredoc/eval/무효화/선행 종결자 전 구문 우회를 «열거 없이» 닫는다(열린→닫힌 세계·S-6). YAML 파싱+byte 대조 = 기존 도구·자작 파서/도달성 분석기 불요. 스텝 메타(shell·continue-on-error·if·timeout)는 닫힌 키 집합. 정본 B 는 sha 불일치 시 `shasum -c` 비-0→`set -euo pipefail` 스텝 실패로 실패 전파 보장(실측 정상 OK/0·변조 FAILED/1). **T-84 ⑬ 재편 = «정본 불일치 클래스»**(⑬a echo·⑬b trailing 주석·⑬c `|| true`·⑬d 도달 불가 호출·⑬e continue-on-error/if·⑬f set +e/trap·**⑬g 선행 종결자**·전부 정본 불일치→UNVERIFIED_REVISION·종수 불변) + 양성(정본 일치) + 정규화 대조군(주석/공백만 다르면 일치). **정직 경계**: 정본 일치 ≠ 런타임 실제 실행(선행 스텝 `PATH`/`env` 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함). ② **#2 #5/#6 부분 (medium) — 비순환 생산 순서**: 활성 UNCHK-008 owner_track 이 `Phase 1`·U-17 하니스 경로가 «D0-A 산출물»이라 Phase 0 가 PREVENTION_ACTIVE 를 소비하기 전에 그 축·하니스를 누가 산출·폐쇄하는지 단일 비순환 순서 부재((D) verbatim 적용이 활성 형제 소비처 미전파·S-22). **UNCHK-008 owner_track `Phase 1`→`Phase 0`**(D0-A 착수 전 선행조건·운영자/인프라·U-17 live 검증·문법 n∈0..7 유효·imprecise_owner_track 불변[단일 phase])·산문 2곳(:4975·:5102) 전파 · **U-17 하니스 «D0-A 산출물»→«pre-D0-A 실체화»**(§12.3.4-R 결속값 sha 957bf49d… 파일 실체화·D0-A 착수 «전» 운영자/인프라가 둔다) · **개발계획 Phase 0 선행조건 불릿에 하니스 파일 실체화 한 줄 추가**(운영자 승인 (D) 개정의 «연장»·같은 대상·같은 pre-D0-A 주체·(D) ②′ verbatim 재기록). **S-22 전수**: «D0-A 산출물» 표기 중 하니스 파일(:5462)만 정정(U15-ENTRY-CHECK·config·원장·계약텍스트는 유지)·UNCHK-023(브랜치 보호 계열이나 git 이력 신뢰 별개 축이라 `Phase 1` 유지)·형제 UNCHK 행 재독. **종수 전파(S-20)**: T-84 14 불변(⑬c 검출 전환·⑬d/e/f 는 ⑬ 하위 케이스)·T-82 20·T-81 19·U-17-c 10값·U-16-d 12단 불변. **§12.3.3**: (A)=v2.20 판정 5건 리터럴(회피 1·해소 3·부분 1)·(B)=v2.21 2건 주장(«어느 것도 해소 아님»·#1 실행 증거 동결 후·#2 형제 전파+개발계획 연장)·(D) 갱신(②′ 연장). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·현행 :4664-4764)·`bound_paths` 2건(계약+개발계획) 편집이므로 O-6 재결속 필요.** **[v2.21 에라타 (동결 `0528a919` 후 증거 실행 `3e0f2429` 적발 — 재결속 전이므로 정정 후 재동결·문언·과잉 차단 방향·fail-open 0)]** 증거(`U17-PREVENTION-CHECK-V221.md`)가 정본 대조 22픽스처 기대 불일치 0(⑬a~⑬g·⑬g B10/B11/B12 사멸·정본 B 런타임 OK/FAILED 전파·#2 순서)이되 문언 결함 후보 1건을 적발했다: **ⓐ E1(P-2·문언·과잉 차단)** 정규화 규칙이 YAML 스칼라 «표기»를 미언급 — 스텝 A(2줄)는 folded `>`+빈 줄이면 우연히 일치하나 **스텝 B(단일 파이프라인)를 `>` folded 로 쓰면 두 줄이 접혀 정본 불일치** → 정직한 워크플로도 red. → 정규화 규칙에 «정본 `run:` 은 literal block scalar(`|`) 표기 전제·`>` folded·인라인은 불일치=fail-closed·작성자는 `|` 사용» 명시(극성: 과잉 차단은 «표기 지정»으로 해소·S-15)·T-84 ⑬ 정규화 대조군을 «`|` 표기 + 주석/빈 줄 차이만»으로 정정(folded 는 A 에만 성립·B 불일치 명시). **종수 불변**(문언). **하니스 byte-identical(`957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d`·:4664-4764)·개발계획 무편집·`bound_paths`(계약만) 재동결.** **증거 결속(S-24)**: 이 에라타 재동결도 addendum 으로 이행(절 범위 `git diff` 공집합 + 영향 변이 재실행 — 스텝 A/B `|` 양성·`>` folded→B 불일치(계약대로 red)·A folded+빈 줄 일치 문언 정합). **심사 미판정 — 동결 후 재결속 대기.** 구현 착수 금지 불변 |
@@ -2891 +2891 @@ RUNTIME/FAULT/REVIEWER 존재성·REV2·A-1/A-2·D0-5에 테스트가 없었다.
-| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 / v2.21 재편 — 심판 #1] 정본 불일치 클래스** — 동일 path/app/head 성공 워크플로 blob 에서 게이트 두 스텝(`tos-gate: run harness`·`tos-gate: verify harness sha256`)의 `run:` 이 **정규화 후 계약 정본(A/B)과 다르면** → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0.  «토큰 존재»가 아니라 «정본 byte 일치»가 관측량이다(구문 우회 전 클래스를 «열거 없이» 닫음·열린→닫힌 세계). **양성(정본 일치)**: `run:` 이 정본 A/B 와 정규형 일치면 red 가 «아니어야» 한다(허용 정본 집합 안이면 통과) · **정규화 대조군**: 주석 줄·빈 줄·trailing 공백·CRLF 만 다른 blob → «일치»(정규화가 결정적으로 흡수). **불일치 하위 케이스(전부 UNVERIFIED_REVISION·종수 불변)**: ⑬a `echo "…경로…"`(경로가 출력 명령 인자 — 정본 아님) · ⑬b `true  # shasum…|grep 957…`(무실행 + trailing 주석 — 정본 아님) · ⑬c `shasum…|grep 957… || true`(대조 뒤 `|| true` 무효화 — 정본 아님; **v2.20 의 «미검출» 기대가 v2.21 에서 «UNVERIFIED_REVISION» 으로 뒤집힘**·증거 V220 §3 ⑬c ACTIVE 기대 갱신) · **⑬d 도달 불가 호출** — `false && bash tools/tos_entry_harness.sh || true`(하니스가 `&&` 피연산자)·`… && bash tools/…`(선행 가드) — 정본 아님 · ⑬e 스텝 `continue-on-error: true`·`if: always()`/`failure()`·**추가 메타 키**(`working-directory`·`env:`·`with:`·`uses:`) 존재(닫힌 메타 키 집합 위배) · ⑬f `set +e`·`trap … ERR`(정본에 없는 줄) · **⑬g 선행 종결자** — `set -euo pipefail; exit 0; bash tools/…`·`exec true`·`[ -n "${SKIP:-}" ] && exit 0`(하니스 호출 «전»에 제어흐름을 종결해 미실행 — 독립 검증 B10/B11/B12 재현; 정본에 그 «실행 줄»이 없어 불일치로 검출). **⑬a~⑬g 는 전부 «정본과 다른 실행 줄»이라 정본 대조가 열거 없이 닫는다** — 자작 도달성 분석기 불요(운영자 «바퀴 재발명 금지»). **정직 경계(잔여)**: 정본 일치는 «런타임 실제 실행»을 증명 못 함(선행 스텝 `PATH`/env 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
+| **T-84** | **U-17 예방 통제 활성 증거** (§12.3.4) | **v2.15 신설 / v2.16 재작성 / [v2.17 재작성 — stop-time BLOCK B3 / v2.19 확장 / v2.20 확장]** — 파라미터화 **14종**. **v2.16 에라타 E2 가 #5 근거만 고치고 이 행을 보지 않아**(S-22) `rulesets=[]`·«머지 커밋 check-runs 0»·«pulls 공집합»이 **같은 턴 실측과 충돌**한 채 남아 있었다 — 행 전체를 재작성한다. ① **live 서버 음성(실측)** — 아티팩트 선언 == 구조 파생(`main`)인 정상 구성에서 `responder=gh` 실조회: `required_status_checks {strict:false, contexts:["test"]}` 이므로 **`PREVENTION_INSUFFICIENT`** · `/rules/branches/main` → `[]`(적용 규칙 0) · `/rulesets` → `[{name:"protect_main", enforcement:"disabled"}]` ⇒ **룰셋은 실재하나 disabled 라 동등물 없음**. **인증된 진짜 음성이며 모의가 아니다**. **[E1 — v2.17 에라타]** 초안은 여기에 «작업 브랜치 → 404 → `PREVENTION_ABSENT`» 를 함께 적었으나, **v2.17 에서 `target_branch` 는 `default_branch` 로 «파생»되므로 그 구성은 ⑤(`TARGET_MISMATCH`)이지 `ABSENT` 가 아니고 실행기로 재현되지 않는다**(증거 실행 적발 — S-22: B1 의 파생 전환이 이 행에 미전파). **«비-default 브랜치 protection → 404»는 «raw probe 관측»으로만 병기**하며 상태값 기대가 아니다 ② **seam 주입(`SIMULATED`)** — `responder` 주입으로 `PREVENTION_ACTIVE`·`INSUFFICIENT`·`UNVERIFIABLE` 모의. **기본 responder 는 `gh api`**. **양성은 운영자가 보호를 설정하기 전까지 실측 불가**임을 숨기지 않는다. **진정성은 §12.3.4 «진실 원천» 절이 «판정 소비자 자신의 조회»로 닫는다** ③ **리비전 검증(실측)** — `/commits/{d}/pulls` → 착지 PR → PR `head.sha` check-runs. 실측: `origin/main` 착지 `11e382fc` 의 check-runs **15건**(push 트리거 워크플로)·`pulls` = PR #636(merged·base main), PR head `7656259d` check-runs 5건에 **`tos-gate` 없음** ⇒ **`PREVENTION_UNVERIFIED_REVISION`**. 미푸시 커밋 → 422 ⇒ `PREVENTION_UNVERIFIABLE` · 푸시됐으나 PR 없는 `be98f075` → `pulls` `[]` ⇒ UNVERIFIED_REVISION ④ **보호 해제 후(stub)** — «countersign 시 ACTIVE → 이후 해제» 후 완료 판정 재조회가 `ABSENT`/`INSUFFICIENT` ⑤ **[v2.17 신설] target 불일치** — 아티팩트가 **다른 저장소/브랜치**를 선언(예: 보호가 걸린 타 repo, 또는 default 아닌 브랜치) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **`D = ∅` 에서도 red 여야 한다** — v2.16 은 이 구성에서 **임의 대상의 보호만으로 ACTIVE** 를 냈다 ⑥ **[v2.17 신설] `app_id` 위조** — `tos-gate` 라는 이름에 `conclusion: success` 이지만 **`app.id` 가 게이트 앱(기본 `15368`)이 아닌** check-run 을 seam 으로 주입 → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **이름만 보는 구현은 통과시키므로 실패한다** ⑦ **[v2.18] 타 앱 고정 required check** — 보호는 있고 `contexts` 에 `tos-gate` 도 있으나 `required_status_checks.checks[]` 의 그 컨텍스트 `app_id` 가 **Actions 가 아닌 앱**(예 99999) → **`PREVENTION_INSUFFICIENT`** + 비-0. **v2.17 은 이름만 봐서 `prot_ok` 를 냈고 `D=∅` 이면 그대로 진입 승인**됐다(심판이 실행기 술어로 재현) ⑧ **[v2.18] same-app wrong-workflow** — **같은 Actions app id** 로 **다른 워크플로**의 잡을 `tos-gate` 로 이름 지어 success 게시 → workflow run 의 `path` 가 `.github/workflows/tos-gate.yml` 이 아니므로 **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **app id 만 보는 구현은 통과시킨다**(실측: PR #636 head 의 5 run 이 전부 동일 app id) ⑨ **[v2.18] 아티팩트 사후 편집** — `P` → D0-A 착수 → 아티팩트 편집 → **`PREVENTION_ARTIFACT_MUTATED`** + 비-0. **`P_last` 를 쓰지 않고 «최초 도입 P» 만 보는 구현은 통과시킨다**  **[v2.20 — 심판 #3] 부모신뢰 TOCTOU 확장**: `P_last` 조상성 소비도 U-16-c 격리 스냅샷 기층을 쓰므로, ㉡ 관측과 조상성 조회 사이 graft 삽입·제거(SIMULATED seam)로 `ARTIFACT_MUTATED`↔`ACTIVE` 를 뒤집는 구현은 격리 스냅샷 안 소비로 fail-closed 됨을 함께 본다(격리 클론 픽스처·종수 불변) ⑩ **[v2.18] 타 원격·타 호스트** — 아티팩트/원격이 **계약 핀**(`github.com/kakao-harris-lee/kis_unified_sts`)과 다른 host 또는 owner/repo 를 가리킴(비-GitHub 호스트의 동일 경로 포함) → **`PREVENTION_TARGET_MISMATCH`** + 비-0. **host 를 버리는 정규화는 통과시킨다** ⑪ **[v2.19 신설 — 심판 F1] 보호 해제 창(off→merge→on) — 연속성** — **live 로 실행하지 않는다**(실측 픽스처가 서버 보호 설정 변경을 요구하므로): v2.16 (a) 방식의 **«캡처된 응답 위 결정적 술어» seam** 으로 SIMULATED 구성한다. 룰셋 응답에 `updated_at` 이 **최초 착지 `merged_at` 보다 늦은** 캡처를 주입 → **`PREVENTION_CONTINUITY_UNVERIFIABLE` + 비-0**(U-17-c). **classic branch protection 만인 캡처**(`updated_at`·`created_at` 부재) → 같은 값(연속성 판정 불가). **`updated_at`·`created_at` ≤ `merged_at` 캡처** → 그 축 통과(다른 축이 성립하면 `PREVENTION_ACTIVE`). **판별력**: 「진입·완료 두 조회가 둘 다 ACTIVE 면 통과」로 접는 구현은 이 SIMULATED 를 통과시켜 실패한다. **live 는 현행 상태 음성만**(오늘 `main` 은 룰셋 `disabled` 라 애초에 `PREVENTION_INSUFFICIENT`). **소비 시각은 «서버 시간»만**(응답의 `updated_at`·`created_at`·PR `merged_at`) — 커밋 author/committer date 는 클라이언트 공급이라 쓰지 않는다. **정직 표기**: 감사 로그 없이 «머지 시점 강제»의 완전 증명은 불가하므로 이 대조군은 **설정 변경의 관측**만 fail-closed 로 승격한다 ⑫ **[v2.19 신설 — 심판 신규 high] `GH_HOST` override — 정본 host 결속** — **live 실행 가능**(GET-only·환경변수만). 소비자는 계약 핀에서 host 를 파생해 **모든 `gh api` 에 `--hostname <핀 host>` 명시 + 자기 환경 `GH_HOST` 를 핀 host 로 설정**한다. 대조군은 `GH_HOST=<타 host>`(+`GH_ENTERPRISE_TOKEN=dummy`) 주입 후 실행 → **상태값이 override 유무와 «불변»**(조회가 핀 host 에 결속)이거나, 핀 host 도달·인증 불가면 **`PREVENTION_UNVERIFIABLE`**(fail-closed). **override 가 상태값을 바꾸면(특히 타 host 응답으로 `PREVENTION_ACTIVE`) 실패** = host 를 `gh` 환경에 위임하는 구현. **심판 실측 프로브**(`GH_HOST=example.invalid … gh api repos/a/b`, exit 1)가 host 없는 명령의 결함을 재현한 그 클래스이며, T-84 ⑩(remote URL 대조만)은 이 축을 잡지 못한다 ⑬ **[v2.20 신설 / v2.21 재편 — 심판 #1] 정본 불일치 클래스** — 동일 path/app/head 성공 워크플로 blob 에서 게이트 두 스텝(`tos-gate: run harness`·`tos-gate: verify harness sha256`)의 `run:` 이 **정규화 후 계약 정본(A/B)과 다르면** → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0.  «토큰 존재»가 아니라 «정본 byte 일치»가 관측량이다(구문 우회 전 클래스를 «열거 없이» 닫음·열린→닫힌 세계). **양성(정본 일치)**: `run:` 이 정본 A/B 와 정규형 일치면 red 가 «아니어야» 한다(허용 정본 집합 안이면 통과) · **정규화 대조군**: **`|` (literal) 표기** 하에서 주석 줄·빈 줄·trailing 공백·CRLF 만 다른 blob → «일치»(정규화가 결정적으로 흡수); `>` folded 는 스텝 A(빈 줄=개행)만 우연 일치·**스텝 B 는 접혀 불일치**(fail-closed)·정본 표기는 `|`([v2.21 에라타 ⓐ/E1]). **불일치 하위 케이스(전부 UNVERIFIED_REVISION·종수 불변)**: ⑬a `echo "…경로…"`(경로가 출력 명령 인자 — 정본 아님) · ⑬b `true  # shasum…|grep 957…`(무실행 + trailing 주석 — 정본 아님) · ⑬c `shasum…|grep 957… || true`(대조 뒤 `|| true` 무효화 — 정본 아님; **v2.20 의 «미검출» 기대가 v2.21 에서 «UNVERIFIED_REVISION» 으로 뒤집힘**·증거 V220 §3 ⑬c ACTIVE 기대 갱신) · **⑬d 도달 불가 호출** — `false && bash tools/tos_entry_harness.sh || true`(하니스가 `&&` 피연산자)·`… && bash tools/…`(선행 가드) — 정본 아님 · ⑬e 스텝 `continue-on-error: true`·`if: always()`/`failure()`·**추가 메타 키**(`working-directory`·`env:`·`with:`·`uses:`) 존재(닫힌 메타 키 집합 위배) · ⑬f `set +e`·`trap … ERR`(정본에 없는 줄) · **⑬g 선행 종결자** — `set -euo pipefail; exit 0; bash tools/…`·`exec true`·`[ -n "${SKIP:-}" ] && exit 0`(하니스 호출 «전»에 제어흐름을 종결해 미실행 — 독립 검증 B10/B11/B12 재현; 정본에 그 «실행 줄»이 없어 불일치로 검출). **⑬a~⑬g 는 전부 «정본과 다른 실행 줄»이라 정본 대조가 열거 없이 닫는다** — 자작 도달성 분석기 불요(운영자 «바퀴 재발명 금지»). **정직 경계(잔여)**: 정본 일치는 «런타임 실제 실행»을 증명 못 함(선행 스텝 `PATH`/env 조작·GitHub 내부·스텝 이름 위조 — 위조 비용↑·닫지 못함) ⑭ **[v2.20 신설 — 심판 #1] 서버 잡 스텝 부재/실패** — blob 구조는 통과하나 서버 `actions/runs/{run_id}/jobs`(또는 `actions/jobs/{job_id}`) 그 잡 `steps[]` 에 계약 리터럴 «스텝 이름»(`tos-gate: run harness`·`tos-gate: verify harness sha256`)이 **부재**하거나 그 스텝 `conclusion != success` → **`PREVENTION_UNVERIFIED_REVISION`** + 비-0. **판별력**: blob 만 보고 서버 스텝 실행 기록을 대조 안 하는 구현은 통과 → 서버 스텝 대조는 red.  **정직 경계**: 스텝 이름·결론은 «서버 기록»이지 «그 스텝의 run 내용을 그대로 실행했다»의 증명이 아니다(⑬+⑭ 는 위조 비용을 올리되 GitHub 내부 실행 간극은 안 닫는다) |
@@ -4398 +4398 @@ closed»로 오분류) → **E15**: 결합을 «`--show-toplevel` 루트 결합
-**v2.20 신규 증거 = `d101eb63`**(`U17`/`U16-…-V220.md` — 기대 전건 일치·문언 에라타 ⓐⓑⓒ 적발·fail-open 0)이며, 그 에라타는 변경 이력 v2.20 에라타 절이 유일 소스다(S-24).  직전 층(v2.19) 증거는 스탬프
+**v2.20 신규 증거 = `d101eb63`**(`U17`/`U16-…-V220.md` — 기대 전건 일치·문언 에라타 ⓐⓑⓒ 적발·fail-open 0)이며, 그 에라타는 변경 이력 v2.20 에라타 절이 유일 소스다(S-24).  **v2.21 신규 증거 = `3e0f2429`**(`U17-…-V221.md` — 정본 대조 22픽스처 0 불일치·문언 에라타 ⓐ[E1 YAML 스칼라 표기] 적발·fail-open 0)이며 그 에라타는 변경 이력 v2.21 에라타 절이 유일 소스다(S-24).  직전 층(v2.19) 증거는 스탬프
@@ -5497 +5497 @@ printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59
-                             동일해야 한다.  **주석·공백만 다른 blob 은 «일치»**(정규화 대조군); «실행되는 줄»이 하나라도
+                             동일해야 한다.  **[v2.21 에라타 ⓐ — E1] 정본 `run:` 은 YAML literal block scalar(`|`) 표기를 전제한다** — `|` 는 개행 보존이나 `>` folded 는 개행을 공백으로 접어(스텝 B 단일 파이프라인이 `set -euo pipefail` 과 한 줄로 접힘) 파싱값이 정본과 달라 «불일치=fail-closed»·인라인도 동일; **D0-A 작성자는 `|` 를 쓴다**(과잉 차단은 «표기 지정»으로 해소·S-15).  **주석·공백만 다른 blob 은 «일치»**(정규화 대조군); «실행되는 줄»이 하나라도
```

### 1-2. s24-proof 2층 (`s24-proof-e1.py` sha256 `5fcb6b7a620dedc67f4a5cf849db371495c7185858770397b5f46d0a75275ec8` · 109행)

① 층은 `git diff -U0` 의 hunk 를 **자동 추출**해 그 여집합을 양 blob 에서 sha256 대조한다(구간 목록을 손으로 적지 않아 «누락» 구조적 불가). ② 층은 각 절을 **각 blob 안에서 리터럴 앵커로** 찾는다(행 번호 하드코딩 금지). ③ 층은 **정본 A/B 코드펜스 자체**를 앵커로 떠서 내용 byte 대조한다.

```text
blob(0528a919:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = d9d45793fa37b3cb578e76a6051c72b8118f3e5b  행수=7531
blob(65cf2635:docs/plans/2026-08-12-tos-phase0-completion-contract-design.md) = 2660b800ab04a2536bdeaa3bf86168b65667b78d  행수=7531

① 무변경 구간 증명 — hunk 5개 (기계 추출): -130,1 +130,1 · -213,1 +213,1 · -2891,1 +2891,1 · -4398,1 +4398,1 · -5497,1 +5497,1
   hunk 여집합 구간별 sha256 대조 (구간을 손으로 적지 않는다 — 누락 불가):
   구간#1: old[1..129] vs new[1..129]  129행/129행  bccbf280af2b737c / bccbf280af2b737c → 동일
   구간#2: old[131..212] vs new[131..212]  82행/82행  3996c5209fb2adec / 3996c5209fb2adec → 동일
   구간#3: old[214..2890] vs new[214..2890]  2677행/2677행  dbb6fbb4f7436614 / dbb6fbb4f7436614 → 동일
   구간#4: old[2892..4397] vs new[2892..4397]  1506행/1506행  81e8d281d7013736 / 81e8d281d7013736 → 동일
   구간#5: old[4399..5496] vs new[4399..5496]  1098행/1098행  4be590ffd5c7d230 / 4be590ffd5c7d230 → 동일
   구간#6: old[5498..7532] vs new[5498..7532]  2035행/2035행  ca8db65443d861d6 / ca8db65443d861d6 → 동일
   ⇒ 변경이 «닿지 않은» 구간 차이 = 0건 (0 이어야 한다)

② 명명 절 증명 — 각 blob 안에서 «리터럴 앵커»로 위치를 찾는다(행 번호 하드코딩 금지)
   절                                              old 행   new 행  판정
  [닿음]
   정규화 규칙 문장 (E1 표기 전제)                          5497    5497  상이 (기대 상이) ✅   sha256 f702e94c9b42 / 1c78dbabf639
   T-84 ⑬ 행 (정규화 대조군 재기술)                        2891    2891  상이 (기대 상이) ✅   sha256 244271f761a5 / 599d3f3d3dcf
   심사 이력 v2.21 행 (1번째 출현)                         130     130  상이 (기대 상이) ✅   sha256 2c4113392f61 / ef9ce51984ca
   변경 이력 v2.21 행 (2번째 출현)                         213     213  상이 (기대 상이) ✅   sha256 5848ae224add / 11175225fb74
   (B) 주 — v2.21 신규 증거                           4398    4398  상이 (기대 상이) ✅   sha256 c2a9cbb92696 / ed3cd53d331a
  [닿지 않음]
   (b)③ 정본 대조 도입 문장                              5467    5467  동일 (기대 동일) ✅   sha256 0f579cfed816 / 0f579cfed816
   서버 잡 스텝 대조 절 (2)                              5514    5514  동일 (기대 동일) ✅   sha256 45631dd8def7 / 45631dd8def7
   하니스 §12.3.4-R 블록 첫 줄                          4664    4664  동일 (기대 동일) ✅   sha256 e2b37d0fbeeb / e2b37d0fbeeb
   하니스 §12.3.4-R 블록 끝 줄                          4764    4764  동일 (기대 동일) ✅   sha256 7c74c97e2e41 / 7c74c97e2e41
   T-82 행 (종수 20)                                2941    2941  동일 (기대 동일) ✅   sha256 a9bd7743aef2 / a9bd7743aef2
   T-81 행 (종수 19)                                2940    2940  동일 (기대 동일) ✅   sha256 6eeb704aa338 / 6eeb704aa338
   U-17-c 상태 10값 정의                              5696    5696  동일 (기대 동일) ✅   sha256 a4770d3b3cef / a4770d3b3cef
   (a) 술어 — required_status_checks               5347    5347  동일 (기대 동일) ✅   sha256 f6e5d2eca7fb / f6e5d2eca7fb
   (α) 연속성 절                                      217     217  동일 (기대 동일) ✅   sha256 d1ecc6575a28 / d1ecc6575a28
   U-16-c c_APP 구조 정의 수식                         7121    7121  동일 (기대 동일) ✅   sha256 dc53f88be2ef / dc53f88be2ef
   U-16 격리 스냅샷 «단일 방법»                           7145    7145  동일 (기대 동일) ✅   sha256 edb7664a2e35 / edb7664a2e35
   UNCHK-008 레지스터 행 (owner_track Phase 0)        6228    6228  동일 (기대 동일) ✅   sha256 1460d28bd4c8 / 1460d28bd4c8
   U-17 하니스 pre-D0-A 실체화 문장                      5480    5480  동일 (기대 동일) ✅   sha256 0511008c9dfb / 0511008c9dfb

③ 정본 A 코드펜스: old :5476-5477 · new :5476-5477 → byte 동일? True
   내용 = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'

③ 정본 B 코드펜스: old :5487-5488 · new :5487-5488 → byte 동일? True
   내용 = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"

④ 하니스 §12.3.4-R 블록(:4664-4764) sha256 — old=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
                                              new=957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d
   계약 리터럴 957bf49d… 와 일치? old=True new=True · 양자 byte-동일? True
```

**판독**: 변경이 닿지 않은 구간 차이 **0건** · 닿은 절 5(전건 «상이») · 닿지 않은 절 14(전건 «동일») · **정본 A/B 코드펜스 byte 동일** · 하니스 블록 byte 동일.
→ **비영향 변이는 `3e0f2429` 증거 그대로 결속**된다(재실행 불요). 아래 §2 는 **영향 변이(스칼라 표기 축)만** 재실행한 기록이다.

## 2. S-24 ② — 영향 변이 재실행 (E1: 정본 `run:` 은 literal block `|` 전제)

| 파일 | sha256 | 행수 | 역할 |
| --- | --- | --- | --- |
| `t8xe1.sh` | `30ae6bf8b25d6ea616ba501a9616fba87c7754392e39433bcc9e966daf65c465` | 154 | 드라이버 — blob 배터리 6 + e2e 3 + 회귀 |
| `mkwf-e1.py` | `a4de457fc0fb111e35fb3ec578be4d11c57a8dafa84b194fa91a25636cacea60` | 39 | 픽스처 생성기 — `mkwf-v221.py` 의 `wf()` 를 import 재사용, 스칼라 표기만 변형 |
| `u17-verify-v221.sh` | `5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727` | 486 | 판정 실행기 (변경 없음 — v2.21 증거와 동일 sha) |
| `wfcanon-v221.py` | `a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d` | 159 | 정본 대조 술어 (변경 없음) |

### 2-1. blob 배터리 — 스칼라 «표기»만 바꾼 6 픽스처

```text
########## ① blob 배터리 — 스칼라 «표기»만 바꾼 6 픽스처 (기대는 생성기가 «미리» 적은 값) ##########
  fixtures=6 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/wf
  id               기대                 실측                 설명
  e1-a-literal     BLOB_OK                BLOB_OK                스텝 A `|` (literal) 양성 — 정본 표기  [OK]
  e1-a-folded      BLOB_OK                BLOB_OK                스텝 A 만 folded `>` + 빈 줄 → 파싱값이 정본 A 와 «우연 일치»  [OK]
  e1-b-literal     BLOB_OK                BLOB_OK                스텝 B `|` (literal) 양성 — 정본 표기  [OK]
  e1-b-folded      UNVERIFIED_REVISION    UNVERIFIED_REVISION    스텝 B folded `>` → 두 줄이 «한 줄로 접힘» → 정본 B 불일치(계약대로 red)  [OK]
  e1-b-folded-bl   BLOB_OK                BLOB_OK                스텝 B folded `>` + 빈 줄 → 개행 보존으로 정본 B 와 «우연 일치»(초안 기대 UNVERIFIED_REVISION 정정)  [OK]
  e1-b-inline      UNVERIFIED_REVISION    UNVERIFIED_REVISION    스텝 B 인라인 평문 스칼라(`;` 결합) → 불일치  [OK]
  ⇒ 기대와 다른 케이스 = 0 건

-- 기제 원문: yq 가 준 파싱값 (folded 가 «접는» 자리) --
  e1-b-literal     parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded      parsed(step B) = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded-bl   parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-inline      parsed(step B) = "set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"

/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 124: syntax error near unexpected token `|'
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 124: `|'
-- 대표 2종 술어 원문 (B  양성 vs B folded 불일치) --
== e1-b-literal ==
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
== e1-b-folded ==
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
  |         run: >
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
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = False  ← 첫 불일치 오프셋 17
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

```

| 픽스처 | 표기 | 기대 | 실측 | 판독 |
| --- | --- | --- | --- | --- |
| `e1-a-literal` | 스텝 A `\|` | BLOB_OK | **BLOB_OK** | 정본 표기 양성 ✅ |
| `e1-a-folded` | 스텝 A `>` + 빈 줄 | BLOB_OK | **BLOB_OK** | 계약이 적은 «스텝 A 우연 일치» 그대로 ✅ |
| `e1-b-literal` | 스텝 B `\|` | BLOB_OK | **BLOB_OK** | 정본 표기 양성 ✅ |
| **`e1-b-folded`** | 스텝 B `>` | UNVERIFIED_REVISION | **UNVERIFIED_REVISION** | **접힘 실측**: 파싱값이 `set -euo pipefail printf …`(한 줄) → 정본 B 불일치 ✅ 계약 E1 대로 red |
| `e1-b-folded-bl` | 스텝 B `>` + 빈 줄 | BLOB_OK *(초안 기대 정정)* | **BLOB_OK** | 빈 줄이 개행을 보존해 **우연 일치**(스텝 A 와 동형) — §5 Q-1 |
| `e1-b-inline` | 스텝 B 인라인 평문(`;`) | UNVERIFIED_REVISION | **UNVERIFIED_REVISION** | 계약 «인라인도 동일» 그대로 ✅ |

**기제(파싱값 원문)** — 접히는 자리와 보존되는 자리가 배터리 안에서 직접 관측된다:

```text
  e1-b-literal     parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded      parsed(step B) = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded-bl   parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-inline      parsed(step B) = "set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
```

### 2-2. e2e (실행기 전체 · SIMULATED seam · blob 표기만 다름)

| # | 표기 | 계약 기대 | 실측 | rc |
| --- | --- | --- | --- | --- |
| ②-1 | 스텝 B `\|`(정본 표기) | `PREVENTION_ACTIVE` | **`PREVENTION_ACTIVE`** | 0 ✅ |
| ②-2 | 스텝 B folded `>` | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |
| ②-3 | 스텝 B 인라인 평문 | `UNVERIFIED_REVISION` | **`PREVENTION_UNVERIFIED_REVISION`** | 1 ✅ |

### 2-3. 회귀 불변

```text
########## ③ 회귀 불변 — v2.21 본 증거의 대표 케이스를 에라타 하에서 재실행 ##########
  id                 기대                 실측
  pos-canonical      BLOB_OK                BLOB_OK  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]

```

추가로 ⑬g 선행 종결자 e2e 가 에라타 하에서도 `PREVENTION_UNVERIFIED_REVISION`/rc 1 로 불변이다(§4 원문 §③-2).

## 3. 실행 기록 (stdout 전문 · rc 포함)

### 3-1. `bash t8xe1.sh` (390행)

```text
t8xe1_utc=2026-08-19T12:35:02Z
sha256(u17-verify-v221.sh)=5410519e58afc9e2258d76382192096da655c96606b815fd70c7d82469fd4727
sha256(wfcanon-v221.py)=a5430e1a593d890f19a36713b9577c15c807a12c4131d45bd2937744255b811d
sha256(mkwf-v221.py)=f0688051749c4ff4ff141a7dd2f148bc7256bd249b8c790762f7230a31e052f5
sha256(mkwf-e1.py)=a4de457fc0fb111e35fb3ec578be4d11c57a8dafa84b194fa91a25636cacea60
git=git version 2.38.0 · yq=yq (https://github.com/mikefarah/yq/) version v4.48.1 · python3=Python 3.14.7

########## ① blob 배터리 — 스칼라 «표기»만 바꾼 6 픽스처 (기대는 생성기가 «미리» 적은 값) ##########
  fixtures=6 → /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/wf
  id               기대                 실측                 설명
  e1-a-literal     BLOB_OK                BLOB_OK                스텝 A `|` (literal) 양성 — 정본 표기  [OK]
  e1-a-folded      BLOB_OK                BLOB_OK                스텝 A 만 folded `>` + 빈 줄 → 파싱값이 정본 A 와 «우연 일치»  [OK]
  e1-b-literal     BLOB_OK                BLOB_OK                스텝 B `|` (literal) 양성 — 정본 표기  [OK]
  e1-b-folded      UNVERIFIED_REVISION    UNVERIFIED_REVISION    스텝 B folded `>` → 두 줄이 «한 줄로 접힘» → 정본 B 불일치(계약대로 red)  [OK]
  e1-b-folded-bl   BLOB_OK                BLOB_OK                스텝 B folded `>` + 빈 줄 → 개행 보존으로 정본 B 와 «우연 일치»(초안 기대 UNVERIFIED_REVISION 정정)  [OK]
  e1-b-inline      UNVERIFIED_REVISION    UNVERIFIED_REVISION    스텝 B 인라인 평문 스칼라(`;` 결합) → 불일치  [OK]
  ⇒ 기대와 다른 케이스 = 0 건

-- 기제 원문: yq 가 준 파싱값 (folded 가 «접는» 자리) --
  e1-b-literal     parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded      parsed(step B) = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-folded-bl   parsed(step B) = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  e1-b-inline      parsed(step B) = "set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"

/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 124: syntax error near unexpected token `|'
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 124: `|'
-- 대표 2종 술어 원문 (B  양성 vs B folded 불일치) --
== e1-b-literal ==
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
== e1-b-folded ==
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
  |         run: >
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
  WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  WF-C4 [B/verify sha256] byte 일치    = False  ← 첫 불일치 오프셋 17
  WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  RESULT=UNVERIFIED_REVISION

########## ② e2e 1쌍 — 같은 픽스처 저장소·같은 seam, blob 표기만 다르다 ##########
  W(PR head)=a7ce138f11431caf9cea0f11c4803faaad3878af  d=accab94e58b9daadac1981648055c90f5b9f50b3
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 135: syntax error near unexpected token `|'
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 135: `|'

########## ②-1 정본 표기  양성 ⇒ PREVENTION_ACTIVE + rc 0 ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * accab94 2026-08-19T21:35:03+09:00 D0-A: introduce config/tos_completion.yaml
  * a7ce138 2026-08-19T21:35:03+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5371c4a 2026-08-19T21:35:03+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c4531e2 2026-08-19T21:35:03+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/pos bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=accab94e58b9daadac1981648055c90f5b9f50b3
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QD7r7RuFF4/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=accab94e58b9daadac1981648055c90f5b9f50b3 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QD7r7RuFF4/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/pos capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.yJ32qgNWvh
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/pos — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QD7r7RuFF4/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QD7r7RuFF4/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:35:05Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:35:05Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:35:05Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:35:05Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:35:05Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:35:05Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] |D|=1 D=[accab94e58b9daadac1981648055c90f5b9f50b3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.QD7r7RuFF4/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/accab94e58b9daadac1981648055c90f5b9f50b3/pulls  utc=2026-08-19T12:35:06Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"a7ce138f11431caf9cea0f11c4803faaad3878af"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/a7ce138f11431caf9cea0f11c4803faaad3878af/check-runs  utc=2026-08-19T12:35:06Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:35:06Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:35:06Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=a7ce138f11431caf9cea0f11c4803faaad3878af  utc=2026-08-19T12:35:06Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "f7c31a83244d265bd05c1c67b67d3f6a79dbc335", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHwKICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@a7ce138f11431caf9cea0f11c4803faaad3878af (encoding=base64 size=441):
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
U17-B6 repos/kakao-harris-lee/kis_unified_sts/actions/runs/424242/jobs  utc=2026-08-19T12:35:07Z  http=200  x-github-request-id=
  | {"total_count":1,"jobs":[{"id":900001,"run_id":424242,"name":"tos-gate","status":"completed","conclusion":"success","head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","steps":[{"name":"Set up job","conclusion":"success","number":1},{"name":"tos-gate: run harness","conclusion":"success","number":2},{"name":"tos-gate: verify harness sha256","conclusion":"success","number":3}]}]}
  | WF-S1 서버 jobs[] 이름 = ['tos-gate']
  | WF-S2 게이트 잡 conclusion = 'success'
  | WF-S3 서버 steps[] = [('Set up job', 'success'), ('tos-gate: run harness', 'success'), ('tos-gate: verify harness sha256', 'success')]
  | WF-S5 서버 층 판정 = SERVER_OK
  | RESULT=SERVER_OK
U17-B5x 보조(선택·판정 미소비): 로컬 git show a7ce138f11431caf9cea0f11c4803faaad3878af:.github/workflows/tos-gate.yml → 204d47144a9323df20bcc6ef908fec645f1647f0
U17-B d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af merged_at=2026-08-10T00:00:00Z: name/conclusion/app.id=15368/head_sha/suite/workflow(path·head)/blob 정본 대조(정본 A·B byte 일치)/서버 잡 steps[] 전부 일치
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_ACTIVE
reason=(a) 술어 충족(checks[].app_id==Actions 15368) ∧ 핀 원격 존재·선언 대조 일치 ∧ [C6] 핀 host 결속(--hostname github.com · GH_HOST 재핀) ∧ countersign 유효 ∧ [E9] |P_last|=1 ∧ ∀d∈D: x_last ⊰ d ∧ 소비 blob==blob(x_last) ∧ (b) 전 리비전 검증(|D|=1) ∧ (α) 연속성 성립(t_land=2026-08-10T00:00:00Z) — responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/pos
u17_rc=0
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 138: syntax error near unexpected token `newline'
/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/t8xe1.sh: command substitution: line 138: `>'

########## ②-2 스텝 B folded  ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 (계약 E1 대로 red) ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * accab94 2026-08-19T21:35:03+09:00 D0-A: introduce config/tos_completion.yaml
  * a7ce138 2026-08-19T21:35:03+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5371c4a 2026-08-19T21:35:03+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c4531e2 2026-08-19T21:35:03+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/fold bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=accab94e58b9daadac1981648055c90f5b9f50b3
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pw9Y5hRuUJ/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=accab94e58b9daadac1981648055c90f5b9f50b3 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pw9Y5hRuUJ/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/fold capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.OvlatJY7Hu
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/fold — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pw9Y5hRuUJ/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pw9Y5hRuUJ/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:35:08Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:35:08Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:35:09Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:35:09Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:35:09Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:35:09Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] |D|=1 D=[accab94e58b9daadac1981648055c90f5b9f50b3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.pw9Y5hRuUJ/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/accab94e58b9daadac1981648055c90f5b9f50b3/pulls  utc=2026-08-19T12:35:10Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"a7ce138f11431caf9cea0f11c4803faaad3878af"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/a7ce138f11431caf9cea0f11c4803faaad3878af/check-runs  utc=2026-08-19T12:35:10Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:35:10Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:35:10Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=a7ce138f11431caf9cea0f11c4803faaad3878af  utc=2026-08-19T12:35:10Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "41f424ea38fd4bcf92ef5d021bfceb88b5563bf8", "size": 441, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46ID4KICAgICAgICAgIHNldCAtZXVvIHBpcGVmYWlsCiAgICAgICAgICBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@a7ce138f11431caf9cea0f11c4803faaad3878af (encoding=base64 size=441):
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
  |         run: >
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
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -\n"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = False  ← 첫 불일치 오프셋 17
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## ②-3 스텝 B 인라인 평문 스칼라 ⇒ PREVENTION_UNVERIFIED_REVISION ##########
-- remotes --
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (fetch)
  | origin	https://github.com/kakao-harris-lee/kis_unified_sts.git (push)
-- artifact @HEAD --
  | owner_repo: kakao-harris-lee/kis_unified_sts
  | target_branch: main
  | tos_gate_check: tos-gate
  | operator_countersign: "operator 2026-08-19T00:00:00Z"   # SIMULATED test fixture
  * accab94 2026-08-19T21:35:03+09:00 D0-A: introduce config/tos_completion.yaml
  * a7ce138 2026-08-19T21:35:03+09:00 W: add .github/workflows/tos-gate.yml (SIMULATED)
  * 5371c4a 2026-08-19T21:35:03+09:00 P: D0A-PREVENTION-CONTROL (SIMULATED; declaration keys present)
  * c4531e2 2026-08-19T21:35:03+09:00 seed
$ U17_RESPONDER=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/inline bash u17-verify-v221.sh <fixture>
U17-SNAP 원 저장소 관측(㉡ «리뷰 보조»로 격하): replace -l=[ ] · /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git/info/grafts=no · is_shallow=false · entry HEAD=accab94e58b9daadac1981648055c90f5b9f50b3
U17-SNAP $ GIT_NO_REPLACE_OBJECTS=1 git clone --no-local --no-hardlinks /private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob /var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1DZoqoK6NJ/snap
U17-SNAP clone rc=0
U17-SNAP canary(스냅샷 «안»): HEAD=accab94e58b9daadac1981648055c90f5b9f50b3 · replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1DZoqoK6NJ/snap/.git/info/grafts=no · is_shallow=false · ㉠(cat-file 부모 == %P) 불일치 0건 / 커밋 4개
U17-0 target=kakao-harris-lee/kis_unified_sts@main
U17-0 pin=github.com/kakao-harris-lee/kis_unified_sts remotes: origin=github.com/kakao-harris-lee/kis_unified_sts match=origin | actions_app_id=15368 (apps/github-actions http=200) | responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/inline capture_dir=/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.T69HhpLcOs
U17-H [C6] pin_host=github.com (계약 핀에서 파생) · 상속 GH_HOST=∅(미설정) → 현행 GH_HOST=github.com · auth 전제 `gh auth status --hostname github.com` → mode=simulated rc=0
  | (responder=file:/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/seam8xe1/inline — live 조회 없음: 주입 응답 위 결정적 술어)
U17-PU [PARENTS-UNTRUSTED] ㉡ 전역 관측: git replace -l=[ ] · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1DZoqoK6NJ/snap/.git/info/grafts(--git-path 파생)=no · ㉢ is_shallow=false · /private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1DZoqoK6NJ/snap/.git/shallow(--git-path 파생) 목록=[ ] · git-dir=/private/tmp/claude-503/-Users-harris-Development-private-kis-unified-sts/159918e8-47df-4978-bf11-b22f19e50240/scratchpad/v221-evidence/fx8xe1/blob/.git · 무력화 GIT_NO_REPLACE_OBJECTS=1 · ㉠ 주 판별=git --no-replace-objects cat-file commit <x> parent 줄
U17-A00 apps/github-actions  utc=2026-08-19T12:35:12Z  http=200  x-github-request-id=
  | {"id":15368,"slug":"github-actions","name":"GitHub Actions"}
U17-A0 repos/kakao-harris-lee/kis_unified_sts  utc=2026-08-19T12:35:12Z  http=200  x-github-request-id=  (.default_branch=main)
U17-T declared-vs-pin: 일치/선언 없음 (declared owner_repo=kakao-harris-lee/kis_unified_sts target_branch=main host=∅(선택 키 부재 → 핀 host 유일 소스))
U17-A1 repos/kakao-harris-lee/kis_unified_sts/branches/main/protection  utc=2026-08-19T12:35:12Z  http=404  x-github-request-id=
  | {"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection","status":"404"}
U17-A2 repos/kakao-harris-lee/kis_unified_sts/rules/branches/main  utc=2026-08-19T12:35:12Z  http=200  x-github-request-id=
  | [{"type":"required_status_checks","ruleset_id":42,"ruleset_source_type":"Repository","parameters":{"strict_required_status_checks_policy":true,"required_status_checks":[{"context":"tos-gate","integration_id":15368}]}},{"type":"pull_request","ruleset_id":42},{"type":"non_fast_forward","ruleset_id":42},{"type":"deletion","ruleset_id":42}]
U17-A3 repos/kakao-harris-lee/kis_unified_sts/rulesets  utc=2026-08-19T12:35:12Z  http=200  x-github-request-id=
  | [{"id":42,"name":"protect_main","target":"branch","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z"}]
U17-A4 repos/kakao-harris-lee/kis_unified_sts/rulesets/42  utc=2026-08-19T12:35:12Z  http=200  x-github-request-id=
  | {"id":42,"name":"protect_main","target":"branch","source_type":"Repository","enforcement":"active","created_at":"2026-08-01T00:00:00Z","updated_at":"2026-08-05T00:00:00Z","bypass_actors":[],"rules":[{"type":"required_status_checks"},{"type":"pull_request"},{"type":"non_fast_forward"},{"type":"deletion"}]}
U17-α0 적용 룰셋(연속성 입력우주) = [42]  (rules/branches/main 의 ruleset_id · rulesets 목록 전체=[42])
u17_live_state=PREVENTION_ACTIVE
u17_live_reason=(a) 술어 충족: classic=False ruleset=True
P_first(집합·|1|)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] P_last(집합·|1|·blob=c413b5fb0bcabcd67d4b6c34f3f9e5ac3e1dd870)=[5371c4af01e82e028aafa0089364bb8185a0f992 ] |D|=1 D=[accab94e58b9daadac1981648055c90f5b9f50b3 ]  [E9 ∀-부모]
U17-PU㉢ [E12] ㉢ 먼저 — 얕은 경계로 «특정»돼 국소 귀속된 불일치 0건=[]
U17-PU㉠ 재파생 대조: 검사 후보 2건 · «남는» 전역 불일치 0건=[]
U17-SHALLOW is_shallow=false shallow 목록(/private/var/folders/mh/c3r1z1fj6l9_7vfsn7bq9dqr0000gq/T/tmp.1DZoqoK6NJ/snap/.git/shallow)=[ ] · 후보 우주 내 경계 커밋: D=[ ](0건) P=[ ](0건)  (E6: 전역 단축 아님 — 경로별 국소 판정)
U17-B1 repos/kakao-harris-lee/kis_unified_sts/commits/accab94e58b9daadac1981648055c90f5b9f50b3/pulls  utc=2026-08-19T12:35:13Z  http=200  x-github-request-id=
  | [{"number":9999,"state":"closed","merged_at":"2026-08-10T00:00:00Z","base":{"ref":"main"},"head":{"sha":"a7ce138f11431caf9cea0f11c4803faaad3878af"}}]
U17-B2 repos/kakao-harris-lee/kis_unified_sts/commits/a7ce138f11431caf9cea0f11c4803faaad3878af/check-runs  utc=2026-08-19T12:35:13Z  http=200  x-github-request-id=
  | {"total_count":2,"check_runs":[{"name":"test","conclusion":"success","app":{"id":15368},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}},{"name":"tos-gate","conclusion":"success","app":{"id":15368,"slug":"github-actions"},"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite":{"id":777001}}]}
U17-B3 repos/kakao-harris-lee/kis_unified_sts/check-suites/777001  utc=2026-08-19T12:35:13Z  http=200  x-github-request-id=
  | {"id":777001,"head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","app":{"id":15368,"slug":"github-actions"},"status":"completed","conclusion":"success"}
U17-B4 repos/kakao-harris-lee/kis_unified_sts/actions/runs?check_suite_id=777001  utc=2026-08-19T12:35:13Z  http=200  x-github-request-id=
  | {"total_count":1,"workflow_runs":[{"id":424242,"name":"tos-gate","path":".github/workflows/tos-gate.yml","head_sha":"a7ce138f11431caf9cea0f11c4803faaad3878af","check_suite_id":777001,"conclusion":"success"}]}
U17-B5 repos/kakao-harris-lee/kis_unified_sts/contents/.github/workflows/tos-gate.yml?ref=a7ce138f11431caf9cea0f11c4803faaad3878af  utc=2026-08-19T12:35:14Z  http=200  x-github-request-id=
  | {"name": "tos-gate.yml", "path": ".github/workflows/tos-gate.yml", "sha": "b055baec7bb2191b44797e540238df4832571a65", "size": 420, "type": "file", "encoding": "base64", "content": "bmFtZTogdG9zLWdhdGUKb246IFtwdWxsX3JlcXVlc3RdCmpvYnM6CiAgdG9zLWdhdGU6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0CiAgICBzdGVwczoKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHJ1biBoYXJuZXNzIgogICAgICAgIHJ1bjogfAogICAgICAgICAgc2V0IC1ldW8gcGlwZWZhaWwKICAgICAgICAgIGJhc2ggdG9vbHMvdG9zX2VudHJ5X2hhcm5lc3Muc2gKICAgICAgLSBuYW1lOiAidG9zLWdhdGU6IHZlcmlmeSBoYXJuZXNzIHNoYTI1NiIKICAgICAgICBydW46IHNldCAtZXVvIHBpcGVmYWlsOyBwcmludGYgJyVzICB0b29scy90b3NfZW50cnlfaGFybmVzcy5zaFxuJyA5NTdiZjQ5ZGE4ZmM2YWUzOWY5N2FiZTY3OTQxMWFmZWFhNWE1OWY3MDdmMzViZjNiM2E4YzZmOWRlMTQxZjBkIHwgc2hhc3VtIC1hIDI1NiAtYyAt\n"}
U17-B5 decoded .github/workflows/tos-gate.yml@a7ce138f11431caf9cea0f11c4803faaad3878af (encoding=base64 size=420):
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
  |         run: set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -
  | WF-C0 YAML 파서 = yq -o=json (기존 도구) · 대조 = 정규화 후 byte 비교 · 대상 = jobs.tos-gate.steps[] 의 run: «뿐»
  | WF-C0 정본 A = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C0 정본 B = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C1 steps[] 이름 = ['tos-gate: run harness', 'tos-gate: verify harness sha256']
  | WF-C2 [A/run harness] run 원문     = 'set -euo pipefail\nbash tools/tos_entry_harness.sh\n'
  | WF-C3 [A/run harness] 정규형       = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C3 [A/run harness] 정본         = 'set -euo pipefail\nbash tools/tos_entry_harness.sh'
  | WF-C4 [A/run harness] byte 일치    = True
  | WF-C5 [A/run harness] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C2 [B/verify sha256] run 원문     = "set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정규형       = "set -euo pipefail; printf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C3 [B/verify sha256] 정본         = "set -euo pipefail\nprintf '%s  tools/tos_entry_harness.sh\\n' 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d | shasum -a 256 -c -"
  | WF-C4 [B/verify sha256] byte 일치    = False  ← 첫 불일치 오프셋 17
  | WF-C5 [B/verify sha256] 스텝 키 = ['name', 'run'] · 메타 닫힌 집합 = True
  | WF-C6 blob 층 판정 = UNVERIFIED_REVISION
  | RESULT=UNVERIFIED_REVISION
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1

########## ③ 회귀 불변 — v2.21 본 증거의 대표 케이스를 에라타 하에서 재실행 ##########
  id                 기대                 실측
  pos-canonical      BLOB_OK                BLOB_OK  [OK]
  ctrl-comments      BLOB_OK                BLOB_OK  [OK]
  ctrl-crlf          BLOB_OK                BLOB_OK  [OK]
  13g-exit0          UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13c-ortrue         UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  13a-echo           UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]
  nbsp-trailing      UNVERIFIED_REVISION    UNVERIFIED_REVISION  [OK]

########## ③-2 회귀 e2e — ⑬g 선행 종결자 (에라타 하에서도 UNVERIFIED_REVISION) ##########
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-08-10T00:00:00Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 42: ruleset 42 created_at=2026-08-01T00:00:00+00:00 ≤ t_land ∧ updated_at=2026-08-05T00:00:00+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)③ d=accab94e58b9daadac1981648055c90f5b9f50b3 head=a7ce138f11431caf9cea0f11c4803faaad3878af 정본 불일치 — 정규화 후 run: 이 계약 정본 A/B 와 byte 다름 또는 닫힌 메타 키 위배 (T-84 ⑬) [수집 1건 중 전순서 최소]
u17_rc=1
```

## 4. 드라이버·픽스처 생성기 원문

### 4-1. `t8xe1.sh` (sha256 `30ae6bf8b25d6ea616ba501a9616fba87c7754392e39433bcc9e966daf65c465` · 154행)

```bash
#!/usr/bin/env bash
# t8xe1.sh — v2.21 «에라타 재동결 65cf2635» S-24 ② 영향 변이 (E1: 정본 run: 은 literal block `|` 전제)
#   blob 배터리 6종(A `|`/A folded/B `|`/B folded/B folded+빈 줄/B 인라인) + e2e 1쌍 + 회귀 불변.
#   GET-only(seam) · 서버 쓰기 0 · 픽스처는 scratchpad 독립 git repo.
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
EX="$SP/u17-verify-v221.sh"; WFS="$SP/wfcanon-v221.py"
FX="$SP/fx8xe1"; SEAM="$SP/seam8xe1"
rm -rf "$FX" "$SEAM"; mkdir -p "$FX" "$SEAM"
printf 't8xe1_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for f in "$EX" "$WFS" "$SP/mkwf-v221.py" "$SP/mkwf-e1.py"; do printf 'sha256(%s)=%s\n' "$(basename "$f")" "$(shasum -a 256 "$f" | cut -d" " -f1)"; done
printf 'git=%s · yq=%s · python3=%s\n' "$(git --version)" "$(yq --version)" "$(python3 -V)"
inj_wf(){ printf '%s' "$2" > "$1/wf.txt"; inject "$1" "repos/$OR/contents/$WF?ref=$3" 200 "$(contents_json "$1/wf.txt" "$(git hash-object "$1/wf.txt")" "$WF")"; }

########################################################################
sec "① blob 배터리 — 스칼라 «표기»만 바꾼 6 픽스처 (기대는 생성기가 «미리» 적은 값)"
python3 "$SP/mkwf-e1.py" "$FX/wf" | sed 's/^/  /'
printf '  %-16s %-22s %-22s %s\n' "id" "기대" "실측" "설명"
FAIL=0
while IFS='|' read -r cid exp desc; do
  got=$(python3 "$WFS" blob "$FX/wf/$cid.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  mark=OK; [ "$got" = "$exp" ] || { mark="MISMATCH"; FAIL=$((FAIL+1)); }
  printf '  %-16s %-22s %-22s %s  [%s]\n' "$cid" "$exp" "$got" "$desc" "$mark"
done < "$FX/wf/INDEX.txt"
echo "  ⇒ 기대와 다른 케이스 = $FAIL 건"
echo
echo "-- 기제 원문: yq 가 준 파싱값 (folded 가 «접는» 자리) --"
for c in e1-b-literal e1-b-folded e1-b-folded-bl e1-b-inline; do
  printf '  %-16s parsed(step B) = %s\n' "$c" "$(yq -o=json '.jobs."tos-gate".steps[1].run' "$FX/wf/$c.yml")"
done
echo
echo "-- 대표 2종 술어 원문 (B `|` 양성 vs B folded 불일치) --"
for c in e1-b-literal e1-b-folded; do echo "== $c =="; sed 's/^/  | /' "$FX/wf/$c.yml"; python3 "$WFS" blob "$FX/wf/$c.yml" 2>&1 | sed 's/^/  /'; done

########################################################################
sec "② e2e 1쌍 — 같은 픽스처 저장소·같은 seam, blob 표기만 다르다"
RB="$FX/blob"; mk "$RB"; art "$RB" "$OR" main >/dev/null; WHB=$(wf "$RB" ok); DB=$(d0a "$RB")
echo "  W(PR head)=$WHB  d=$DB"
e2e(){ local S1="$SEAM/$2"; seam_ruleset "$S1" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z
  rev_seam "$S1" "$DB" "$WHB" 777001 "$TLAND" ok ok
  inj_wf "$S1" "$(cat "$FX/wf/$1.yml")" "$WHB"; run "$RB" "file:$S1"; }

sec "②-1 정본 표기 `|` 양성 ⇒ PREVENTION_ACTIVE + rc 0"
e2e e1-b-literal pos

sec "②-2 스텝 B folded `>` ⇒ PREVENTION_UNVERIFIED_REVISION + 비-0 (계약 E1 대로 red)"
e2e e1-b-folded fold

sec "②-3 스텝 B 인라인 평문 스칼라 ⇒ PREVENTION_UNVERIFIED_REVISION"
e2e e1-b-inline inline

########################################################################
sec "③ 회귀 불변 — v2.21 본 증거의 대표 케이스를 에라타 하에서 재실행"
printf '  %-18s %-22s %s\n' "id" "기대" "실측"
for c in pos-canonical ctrl-comments ctrl-crlf 13g-exit0 13c-ortrue 13a-echo nbsp-trailing; do
  exp=$(grep "^$c|" "$SP/wf/INDEX.txt" | cut -d'|' -f2)
  got=$(python3 "$WFS" blob "$SP/wf/$c.yml" 2>&1 | sed -n 's/^RESULT=//p' | tail -1)
  printf '  %-18s %-22s %s  [%s]\n' "$c" "$exp" "$got" "$( [ "$got" = "$exp" ] && echo OK || echo MISMATCH )"
done
sec "③-2 회귀 e2e — ⑬g 선행 종결자 (에라타 하에서도 UNVERIFIED_REVISION)"
S3="$SEAM/g"; seam_ruleset "$S3" 42 2026-08-01T00:00:00Z 2026-08-05T00:00:00Z; rev_seam "$S3" "$DB" "$WHB" 777001 "$TLAND" ok ok
inj_wf "$S3" "$(cat "$SP/wf/13g-exit0.yml")" "$WHB"; run "$RB" "file:$S3" | tail -6
```

### 4-2. `mkwf-e1.py` (sha256 `a4de457fc0fb111e35fb3ec578be4d11c57a8dafa84b194fa91a25636cacea60` · 39행)

```python
#!/usr/bin/env python3
"""mkwf-e1.py — v2.21 에라타 ⓐ(E1) 영향 변이 픽스처 — 스칼라 «표기»만 바꾼다.

mkwf-v221.py 의 `wf()` 빌더를 import 해 재사용한다(바퀴 재발명 금지·같은 바이트 규약).
"""
import importlib.util, os, sys, pathlib
SP = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mk", SP / "mkwf-v221.py")
mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)

RUNA, RUNB, HDR = mk.RUNA, mk.RUNB, mk.HDR

def inline_b():
    """스텝 B 를 «인라인 평문 스칼라»(블록 스칼라 아님)로 — 한 줄이라 개행이 사라진다."""
    a = mk.wf().split("      - name: \"tos-gate: verify harness sha256\"")[0]
    one = RUNB.replace("\n", "; ")
    return a + '      - name: "tos-gate: verify harness sha256"\n        run: ' + one + "\n"

CASES = [
    ("e1-a-literal",   "BLOB_OK",             "스텝 A `|` (literal) 양성 — 정본 표기", mk.wf()),
    ("e1-a-folded",    "BLOB_OK",             "스텝 A 만 folded `>` + 빈 줄 → 파싱값이 정본 A 와 «우연 일치»",
     mk.wf("set -euo pipefail\n\nbash tools/tos_entry_harness.sh", RUNB, scalar_a=">")),
    ("e1-b-literal",   "BLOB_OK",             "스텝 B `|` (literal) 양성 — 정본 표기", mk.wf()),
    ("e1-b-folded",    "UNVERIFIED_REVISION", "스텝 B folded `>` → 두 줄이 «한 줄로 접힘» → 정본 B 불일치(계약대로 red)",
     mk.wf(RUNA, RUNB, scalar_b=">")),
    # [실측 정정] 초안 기대는 UNVERIFIED_REVISION 이었으나 «빈 줄이 개행을 보존»해 정본과 우연 일치한다
    # (스텝 A 의 «우연 일치»와 동형).  기대값을 실측·설명에 맞춰 정정하고 그 사실을 증거에 남긴다.
    ("e1-b-folded-bl", "BLOB_OK",             "스텝 B folded `>` + 빈 줄 → 개행 보존으로 정본 B 와 «우연 일치»(초안 기대 UNVERIFIED_REVISION 정정)",
     mk.wf(RUNA, RUNB.replace("\n", "\n\n"), scalar_b=">")),
    ("e1-b-inline",    "UNVERIFIED_REVISION", "스텝 B 인라인 평문 스칼라(`;` 결합) → 불일치", inline_b()),
]

if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); idx = []
    for cid, exp, desc, text in CASES:
        open(os.path.join(out, cid + ".yml"), "wb").write(text.encode("utf-8"))
        idx.append("%s|%s|%s" % (cid, exp, desc))
    open(os.path.join(out, "INDEX.txt"), "w", encoding="utf-8").write("\n".join(idx) + "\n")
    print("fixtures=%d → %s" % (len(idx), out))
```

### 4-3. `s24-proof-e1.py` (sha256 `5fcb6b7a620dedc67f4a5cf849db371495c7185858770397b5f46d0a75275ec8` · 109행)

```python
#!/usr/bin/env python3
"""s24-proof-e1.py — S-24 ① 2층 증명 (v2.21 동결 0528a919 → 에라타 재동결 65cf2635).

① 무변경 구간 증명(기계 생성): `git diff -U0` 의 hunk 를 «자동» 추출해 그 여집합(=변경이 닿지 않은 구간)을
   양 blob 에서 sha256 비교한다.  구간 목록을 손으로 적지 않으므로 «누락»이 구조적으로 불가능하다.
② 명명 절 증명(리터럴 grep): 각 절을 «각 blob 안에서 리터럴 앵커로» 찾아(행 번호 하드코딩 금지) 그 행을
   sha256 비교한다 — 닿은 절/닿지 않은 절을 각각 명시하고 실측값을 방출한다.
"""
import hashlib, re, subprocess, sys

R = "/Users/harris/Development/private/kis_unified_sts"
C = "docs/plans/2026-08-12-tos-phase0-completion-contract-design.md"
OLD, NEW = "0528a919", "65cf2635"


def blob(rev):
    return subprocess.run(["git", "-C", R, "show", f"{rev}:{C}"], capture_output=True, text=True).stdout.split("\n")


def sha(t):
    return hashlib.sha256("\n".join(t).encode()).hexdigest()


old, new = blob(OLD), blob(NEW)
print(f"blob({OLD}:{C}) = {subprocess.run(['git','-C',R,'rev-parse',f'{OLD}:{C}'],capture_output=True,text=True).stdout.strip()}  행수={len(old)-1}")
print(f"blob({NEW}:{C}) = {subprocess.run(['git','-C',R,'rev-parse',f'{NEW}:{C}'],capture_output=True,text=True).stdout.strip()}  행수={len(new)-1}")

d = subprocess.run(["git", "-C", R, "diff", "-U0", f"{OLD}..{NEW}", "--", C], capture_output=True, text=True).stdout
hunks = []
for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", d, re.M):
    o1, oc, n1, nc = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
    hunks.append((o1, oc, n1, nc))
print(f"\n① 무변경 구간 증명 — hunk {len(hunks)}개 (기계 추출): " +
      " · ".join(f"-{o1},{oc} +{n1},{nc}" for o1, oc, n1, nc in hunks))
print("   hunk 여집합 구간별 sha256 대조 (구간을 손으로 적지 않는다 — 누락 불가):")
po = pn = 0
bad = 0
for i, (o1, oc, n1, nc) in enumerate(hunks + [(len(old) + 1, 0, len(new) + 1, 0)], 1):
    so, sn = old[po:o1 - 1], new[pn:n1 - 1]
    h1, h2 = sha(so), sha(sn)
    ok = "동일" if h1 == h2 else "상이(!!)"
    if h1 != h2:
        bad += 1
    print(f"   구간#{i}: old[{po+1}..{o1-1}] vs new[{pn+1}..{n1-1}]  {len(so)}행/{len(sn)}행  {h1[:16]} / {h2[:16]} → {ok}")
    po, pn = o1 - 1 + oc, n1 - 1 + nc
print(f"   ⇒ 변경이 «닿지 않은» 구간 차이 = {bad}건 (0 이어야 한다)")

ANCH_TOUCHED = [
    ("정규화 규칙 문장 (E1 표기 전제)", "동일해야 한다."),
    ("T-84 ⑬ 행 (정규화 대조군 재기술)", "**T-84** | **U-17 예방 통제 활성 증거**"),
    ("심사 이력 v2.21 행 (1번째 출현)", "| **v2.21** |", 0),
    ("변경 이력 v2.21 행 (2번째 출현)", "| **v2.21** |", 1),
    ("(B) 주 — v2.21 신규 증거", "**v2.20 신규 증거 = `d101eb63`**"),
]
ANCH_UNTOUCHED = [
    ("(b)③ 정본 대조 도입 문장", "blob «정본 대조»"),
    ("서버 잡 스텝 대조 절 (2)", "**서버 잡 스텝 대조** — ①에서 얻은"),
    ("하니스 §12.3.4-R 블록 첫 줄", "#!/usr/bin/env bash"),
    ("하니스 §12.3.4-R 블록 끝 줄", 'emit ENTRY_OK "R-0~R-7 전부 기대와 일치"'),
    ("T-82 행 (종수 20)", "| **T-82** | **U-16 `closable=NO` 전이 provenance**"),
    ("T-81 행 (종수 19)", "| **T-81** | **U-15 P-0 후 재진입**"),
    ("U-17-c 상태 10값 정의", "U-17-c  상태  prevention_control_state"),
    ("(a) 술어 — required_status_checks", "TOS 게이트 체크 이름  아티팩트가 **파라미터로 선언**"),
    ("(α) 연속성 절", "룰셋 `created_at ≤ merged_at"),
    ("U-16-c c_APP 구조 정의 수식", "c_APP(a) = { x ⊑ HEAD :"),
    ("U-16 격리 스냅샷 «단일 방법»", "**단일 방법으로 고정**"),
    ("UNCHK-008 레지스터 행 (owner_track Phase 0)", "| UNCHK-008 |"),
    ("U-17 하니스 pre-D0-A 실체화 문장", "하니스 «파일»은 «pre-D0-A 실체화»"),
]


def find(lines, anchor, label):
    hit = [i for i, l in enumerate(lines) if anchor in l]
    return hit


print("\n② 명명 절 증명 — 각 blob 안에서 «리터럴 앵커»로 위치를 찾는다(행 번호 하드코딩 금지)")
print(f"   {'절':44s} {'old 행':>7s} {'new 행':>7s}  판정")
for tag, anchors in (("닿음", ANCH_TOUCHED), ("닿지 않음", ANCH_UNTOUCHED)):
    print(f"  [{tag}]")
    for item in anchors:
        label, anchor = item[0], item[1]
        idx = item[2] if len(item) > 2 else 0
        ho, hn = find(old, anchor, label), find(new, anchor, label)
        ho, hn = ho[idx:], hn[idx:]
        if not ho or not hn:
            print(f"   {label:42s} {'∅' if not ho else ho[0]+1:>7} {'∅' if not hn else hn[0]+1:>7}  앵커 미발견(!!)")
            continue
        so, sn = old[ho[0]], new[hn[0]]
        same = "동일" if so == sn else "상이"
        exp = "상이" if tag == "닿음" else "동일"
        mark = "✅" if same == exp else "❌ 기대와 다름"
        print(f"   {label:42s} {ho[0]+1:>7} {hn[0]+1:>7}  {same} (기대 {exp}) {mark}   sha256 {hashlib.sha256(so.encode()).hexdigest()[:12]} / {hashlib.sha256(sn.encode()).hexdigest()[:12]}")

# ③ 정본 A/B 코드펜스 — 각 blob 안에서 «리터럴 앵커»로 펜스를 찾아 내용 자체를 대조한다
def fence(lines, anchor):
    i = next(k for k, l in enumerate(lines) if anchor in l)
    f = [k for k in range(i, i + 14) if lines[k].strip() == "```"]
    return "\n".join(lines[f[0] + 1:f[1]]), f[0] + 2, f[1]
for lab, anc in (("정본 A", "정본 A** 와 일치"), ("정본 B", "정본 B** 와 일치")):
    ao, o1, o2 = fence(old, anc); an, n1, n2 = fence(new, anc)
    print(f"\n③ {lab} 코드펜스: old :{o1}-{o2} · new :{n1}-{n2} → byte 동일? {ao == an}")
    print(f"   내용 = {ao!r}")

hb_old = subprocess.run(["bash", "-c", f"git -C {R} show {OLD}:{C} | sed -n '4664,4764p' | shasum -a 256"], capture_output=True, text=True).stdout.split()[0]
hb_new = subprocess.run(["bash", "-c", f"git -C {R} show {NEW}:{C} | sed -n '4664,4764p' | shasum -a 256"], capture_output=True, text=True).stdout.split()[0]
print(f"\n④ 하니스 §12.3.4-R 블록(:4664-4764) sha256 — old={hb_old}\n"
      f"                                              new={hb_new}\n"
      f"   계약 리터럴 957bf49d… 와 일치? old={hb_old.startswith('957bf49d')} new={hb_new.startswith('957bf49d')} · 양자 byte-동일? {hb_old==hb_new}")
```

판정 실행기·술어는 **변경 없음** — v2.21 증거(`3e0f2429`) §11 의 원문과 같은 sha256(`u17-verify-v221.sh` `5410519e…` · `wfcanon-v221.py` `a5430e1a…`)이다.

## 5. 관측 보고 · 신규 결함 후보 (등급)

### Q-1 **[관측 — 기대값 정정]** folded `>` 는 «항상» 불일치가 아니다 — 빈 줄을 끼우면 스텝 B 도 우연 일치한다

- 초안 픽스처는 `e1-b-folded-bl`(스텝 B folded + 빈 줄) 을 `UNVERIFIED_REVISION` 으로 기대했으나 **실측은 `BLOB_OK`** 다. 원인은 YAML folded 규칙 — 빈 줄이 개행으로 보존돼 파싱값이 정본 B 와 같아진다(파싱값 원문 §2-1).
- 계약 문언과 충돌하지 않는다: 계약 :5497 은 «`>` folded 는 개행을 공백으로 접어 … 파싱값이 정본과 달라» 라고 적고, T-84 ⑬ 행(:2891)은 «`>` folded 는 스텝 A(빈 줄=개행)만 우연 일치·스텝 B 는 접혀 불일치» 라고 적는다 — **스텝 B 의 «접힘»은 «빈 줄 없는» 표기에 대해 참**이고, 빈 줄을 끼운 folded 는 **스텝 A 와 같은 «우연 일치»** 클래스다.
- 극성: 우연 일치는 **정본과 byte 동일한 파싱값**이므로 fail-open 이 아니다(정본이 관측량이지 표기가 관측량이 아니다). **등급: 관측(증거 기대값 정정 — 계약 변경 불요).** 다만 T-84 ⑬ 문장을 읽는 구현자가 «folded=항상 red» 로 오독할 여지가 있어 기록해 둔다.

### Q-2 **[관측]** E1 은 «표기 지정»으로 과잉 차단을 해소했고 그 방향이 실측과 일치한다

v2.21 증거 P-2 가 든 함정(정직한 작성자가 folded 로 써서 red)은 **«D0-A 작성자는 `|` 를 쓴다»** 라는 표기 지정으로 닫혔다(:5497). 이 addendum 은 그 지정 하에서 **양성 2종(`|`)·red 2종(folded 무-빈줄·인라인)·우연 일치 2종**을 모두 실행해 경계를 고정했다. **등급: 관측(처분 확인).**

### Q-3 **[fail-open/차단 등급 신규 결함 후보 0]**

계약 문언을 그대로 구현했을 때 green 을 내는 새 자리는 없었다. 배터리 6종·e2e 3종·회귀 7종 전건이 기대와 일치했다(기대 불일치 0건).

## 6. 사후 재조회 (서버 무변경 · HEAD 불변)

```text
post_e1_utc=2026-08-19T12:36:26Z
HEAD = 65cf26353d310a8f48a2bd1fce0cedb3de81b4fa  (65cf2635 와 동일? YES)
계약 워킹트리 blob   = 2660b800ab04a2536bdeaa3bf86168b65667b78d  == 65cf2635 blob 2660b800ab04a2536bdeaa3bf86168b65667b78d → 동일
개발계획 워킹트리 blob = 4b2f664f835c4f3c68e4dff8560214aaa70f8969  == 65cf2635 blob 4b2f664f835c4f3c68e4dff8560214aaa70f8969 → 동일 (에라타에서 무변경)
65cf2635..HEAD 두 문서 커밋 = 0건 · 전체 커밋 = 0건
계약 행수 = 7531 · 개발계획 행수 = 580
하니스 sed -n 4664,4764p sha256 = 957bf49da8fc6ae39f97abe679411afeaa5a59f707f35bf3b3a8c6f9de141f0d (계약 리터럴 957bf49d… 일치? YES · 0528a919 과 byte-동일? YES)
워킹트리 두 문서 변경 = 0건
본 저장소 [PARENTS-UNTRUSTED] 관측: replace -l=[] · info/grafts=ABSENT · is_shallow=false
-- 서버 사후 재조회 (GET 1회 · --hostname github.com) --
$ gh api -i --hostname github.com repos/kakao-harris-lee/kis_unified_sts/branches/main/protection    # utc=2026-08-19T12:36:27Z
  | HTTP/2.0 200 OK
  | X-Github-Request-Id: B9DE:201076:CB2AC9:E1708A:6A85A34B
  | {"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection","required_status_checks":{"url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks","strict":false,"contexts":["test"],"contexts_url":"https://api.github.com/repos/kakao-harris-lee/kis_unified_sts/branches/main/protection/required_status_checks
  ⇒ (a) 술어 입력 불변: contexts=["test"] · tos-gate 부재 ⇒ 본 저장소 live 상태값 극성은 v2.20 증거(d101eb63) 와 동일하다
픽스처 격리: scratchpad 독립 저장소 31개 · 본 저장소 worktree 목록 3줄(이 증거는 worktree 0개 생성)
```
